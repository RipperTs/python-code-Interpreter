import subprocess
import uuid
import time
import os
import ast
import re
from concurrent.futures import ThreadPoolExecutor
import asyncio


class CodeExecutor:
    """
    代码执行器
    """
    def __init__(self):
        self.max_workers = int(os.environ.get('MAX_WORKERS', 4))
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.timeout = int(os.environ.get('EXECUTION_TIMEOUT', 30))
        self.docker_image = os.environ.get('DOCKER_IMAGE', 'python-executor:latest')
        # 用于限制同时运行的容器数量
        self.container_semaphore = asyncio.Semaphore(self.max_workers)
        # 常用包及其对应的pip包名（有些包的import名和pip安装名不一致）
        self.package_mapping = {
            'pd': 'pandas',
            'pandas': 'pandas',
            'np': 'numpy',
            'numpy': 'numpy',
            'plt': 'matplotlib',
            'matplotlib': 'matplotlib',
            'sklearn': 'scikit-learn',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'cv2': 'opencv-python',
            'requests': 'requests',
            'bs4': 'beautifulsoup4',
            'seaborn': 'seaborn',
            # 可以继续添加更多包的映射
        }
        # 容器池 - 预先创建并保持一些容器运行
        self.container_pool = []
        self.container_pool_lock = asyncio.Lock()
        # 已安装包的缓存 - 避免重复安装
        self.installed_packages = set()
        # 容器池初始化标志
        self.pool_initialized = False
        
    async def initialize(self):
        """异步初始化方法，用于初始化容器池"""
        if not self.pool_initialized:
            await self._initialize_container_pool()
            self.pool_initialized = True
        
    async def _initialize_container_pool(self):
        """初始化容器池，预先创建一些容器"""
        pool_size = min(self.max_workers, 2)  # 默认预热2个容器或最大工作线程数
        for i in range(pool_size):
            container_id = f"python_exec_pool_{i}"
            cmd = [
                "docker", "run",
                "-d",  # 后台运行
                "--name", container_id,
                "--network=host",
                "--memory=1g",
                "--cpus=1",
                self.docker_image,
                "tail", "-f", "/dev/null"  # 保持容器运行
            ]
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode == 0:
                    async with self.container_pool_lock:
                        self.container_pool.append(container_id)
                    # 预安装常用包
                    await self._preinstall_common_packages(container_id)
            except Exception as e:
                print(f"初始化容器池错误: {str(e)}")
                
    async def _preinstall_common_packages(self, container_id):
        """在容器中预安装常用包"""
        common_packages = ['numpy', 'pandas', 'matplotlib']
        for package in common_packages:
            cmd = [
                "docker", "exec",
                container_id,
                "pip", "install", "--user", package
            ]
            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                await process.communicate()
                self.installed_packages.add(package)
            except Exception:
                pass

    def _detect_imports(self, code):
        """检测代码中的import语句并返回需要安装的包列表"""
        required_packages = set()

        # 解析Python代码
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return list(required_packages)

        # 遍历AST找到所有import语句
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for name in node.names:
                    base_package = name.name.split('.')[0]
                    if base_package in self.package_mapping:
                        required_packages.add(self.package_mapping[base_package])

            elif isinstance(node, ast.ImportFrom):
                base_package = node.module.split('.')[0] if node.module else ''
                if base_package in self.package_mapping:
                    required_packages.add(self.package_mapping[base_package])

        # 检查代码中的直接使用（如 pd.DataFrame）
        for package_name in self.package_mapping:
            pattern = r'\b' + re.escape(package_name) + r'\.'
            if re.search(pattern, code):
                required_packages.add(self.package_mapping[package_name])

        # 过滤掉已安装的包
        return list(required_packages - self.installed_packages)


    async def execute_code(self, code):
        """异步执行代码"""
        # 确保容器池已初始化
        if not self.pool_initialized:
            await self.initialize()
            
        async with self.container_semaphore:  # 限制并发容器数量
            execution_id = str(uuid.uuid4())
            start_time = time.time()
            container_id = None

            try:
                # 尝试从容器池获取容器
                async with self.container_pool_lock:
                    if self.container_pool:
                        container_id = self.container_pool.pop(0)
                
                # 在线程池中准备代码文件
                code_file = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._prepare_code_file,
                    execution_id,
                    code
                )

                # 在线程池中运行代码
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._run_code,
                    execution_id,
                    code_file,
                    container_id
                )

                execution_time = time.time() - start_time

                # 在线程池中清理临时文件
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._cleanup,
                    execution_id
                )
                
                # 如果使用了池中的容器，将其放回池中
                if container_id and container_id.startswith("python_exec_pool_"):
                    async with self.container_pool_lock:
                        self.container_pool.append(container_id)

                return {
                    'result': result.get('output', ''),
                    'error': result.get('error', None),
                    'execution_time': execution_time,
                    'image_url': result.get('image_url', None)
                }

            except Exception as e:
                # 如果使用了池中的容器，将其放回池中
                if container_id and container_id.startswith("python_exec_pool_"):
                    async with self.container_pool_lock:
                        self.container_pool.append(container_id)
                
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._cleanup,
                    execution_id
                )
                return {'error': str(e)}

    def _prepare_code_file(self, execution_id, code):
        """准备代码文件"""
        work_dir = f"/tmp/python_executor/{execution_id}"
        os.makedirs(work_dir, exist_ok=True)
        os.chmod(work_dir, 0o777)

        # 检测需要的包
        required_packages = self._detect_imports(code)
        setup_code = ""
        
        if required_packages:
            # 准备安装脚本 - 只安装尚未安装的包
            setup_code = """
import sys
import subprocess
import pkg_resources

def install_package(package):
    try:
        pkg_resources.require(package)
    except (pkg_resources.DistributionNotFound, pkg_resources.VersionConflict):
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', '--user', package])

"""
            # 添加包安装代码
            for package in required_packages:
                setup_code += f"install_package('{package}')\n"
                # 添加到已安装包集合
                self.installed_packages.add(package)

        # 只有当代码中包含 matplotlib 时才添加设置代码
        if 'plt' in code or 'matplotlib' in code:
            setup_code += """
import matplotlib.pyplot as plt
import matplotlib as mpl

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False
"""
            
            # 在代码末尾添加图表检测和保存代码
            code += """

# 检查是否有图表生成
if 'plt' in globals() and plt.get_fignums():
    plt.savefig('/code/output/result.png', dpi=300, bbox_inches='tight')
    plt.close('all')
"""

        # 组合完整代码
        full_code = setup_code + "\n" + code
        code_file = os.path.join(work_dir, "code.py")
        with open(code_file, 'w') as f:
            f.write(full_code)

        os.chmod(code_file, 0o666)
        # 创建输出目录
        output_dir = os.path.join(work_dir, "output")
        os.makedirs(output_dir, exist_ok=True)
        os.chmod(output_dir, 0o777)
        return code_file

    def _run_code(self, execution_id, code_file, container_id=None):
        """在Docker容器中运行代码"""
        work_dir = f"/tmp/python_executor/{execution_id}"
        output_dir = os.path.join(work_dir, "output")
        
        # 确保输出目录有正确的权限
        os.chmod(output_dir, 0o777)
        
        if container_id:
            # 使用已存在的容器
            return self._run_in_existing_container(execution_id, code_file, output_dir, container_id)
        else:
            # 创建新容器
            return self._run_in_container(execution_id, code_file)

    def _run_in_existing_container(self, execution_id, code_file, output_dir, container_id):
        """在已存在的容器中运行代码"""
        try:
            # 复制代码文件到容器
            copy_cmd = ["docker", "cp", code_file, f"{container_id}:/code/script.py"]
            subprocess.run(copy_cmd, check=True, capture_output=True)
            
            # 复制输出目录到容器
            mkdir_cmd = ["docker", "exec", container_id, "mkdir", "-p", "/code/output"]
            subprocess.run(mkdir_cmd, check=True, capture_output=True)
            
            # 设置权限
            chmod_cmd = ["docker", "exec", container_id, "chmod", "-R", "777", "/code/output"]
            subprocess.run(chmod_cmd, check=True, capture_output=True)
            
            # 执行代码
            exec_cmd = ["docker", "exec", container_id, "python", "/code/script.py"]
            process = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            
            # 复制输出文件回主机
            copy_back_cmd = ["docker", "cp", f"{container_id}:/code/output/.", output_dir]
            subprocess.run(copy_back_cmd, check=True, capture_output=True)
            
            result = {
                'output': process.stdout.strip(),
                'error': process.stderr if process.returncode != 0 else None,
            }
            
            # 处理图片输出
            image_path = os.path.join(output_dir, "result.png")
            if os.path.exists(image_path):
                timestamp = int(time.time())
                image_filename = f"plot_{execution_id}_{timestamp}.png"
                permanent_path = os.path.join(
                    os.environ.get('IMAGE_STORE_PATH', './images'),
                    image_filename
                )
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                os.rename(image_path, permanent_path)
                os.chmod(permanent_path, 0o666)
                result['image_url'] = f"/images/{image_filename}"
                
            # 清理容器中的临时文件
            cleanup_cmd = ["docker", "exec", container_id, "rm", "-f", "/code/script.py"]
            subprocess.run(cleanup_cmd, capture_output=True)
            cleanup_output_cmd = ["docker", "exec", container_id, "rm", "-rf", "/code/output"]
            subprocess.run(cleanup_output_cmd, capture_output=True)
            
            return result
            
        except subprocess.TimeoutExpired:
            # 超时时强制停止进程
            kill_cmd = ["docker", "exec", container_id, "pkill", "-f", "python /code/script.py"]
            subprocess.run(kill_cmd, capture_output=True)
            return {'error': 'Execution timeout'}
        except Exception as e:
            return {'error': str(e)}

    def _run_in_container(self, execution_id, code_file):
        """在新Docker容器中运行代码"""
        work_dir = f"/tmp/python_executor/{execution_id}"
        output_dir = os.path.join(work_dir, "output")
        container_name = f"python_exec_{execution_id}"

        # 确保输出目录有正确的权限
        os.chmod(output_dir, 0o777)

        cmd = [
            "docker", "run",
            "--rm",
            "--name", container_name,  # 为容器指定唯一名称
            "--network=host",
            "--memory=1g",
            "--cpus=1",
            "-v", f"{code_file}:/code/script.py:ro",
            "-v", f"{output_dir}:/code/output",
            self.docker_image,
            "bash", "-c",
            # 在执行Python脚本前，先创建目录并设置权限
            "mkdir -p /code/output && chmod -R 777 /code/output && python /code/script.py"
        ]

        try:
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )

            result = {
                'output': process.stdout.strip(),
                'error': process.stderr if process.returncode != 0 else None,
            }

            # 处理图片输出
            image_path = os.path.join(output_dir, "result.png")
            if os.path.exists(image_path):
                timestamp = int(time.time())
                image_filename = f"plot_{execution_id}_{timestamp}.png"
                permanent_path = os.path.join(
                    os.environ.get('IMAGE_STORE_PATH', './images'),
                    image_filename
                )
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                os.rename(image_path, permanent_path)
                os.chmod(permanent_path, 0o666)
                result['image_url'] = f"/images/{image_filename}"

            return result

        except subprocess.TimeoutExpired:
            # 超时时强制停止并删除容器
            subprocess.run(["docker", "stop", container_name], capture_output=True)
            subprocess.run(["docker", "rm", container_name], capture_output=True)
            return {'error': 'Execution timeout'}
        except Exception as e:
            # 确保清理容器
            subprocess.run(["docker", "stop", container_name], capture_output=True)
            subprocess.run(["docker", "rm", container_name], capture_output=True)
            return {'error': str(e)}

    def _cleanup(self, execution_id):
        """清理临时文件"""
        work_dir = f"/tmp/python_executor/{execution_id}"
        if os.path.exists(work_dir):
            subprocess.run(["rm", "-rf", work_dir])
            
    async def shutdown(self):
        """关闭执行器，清理所有资源"""
        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 停止并删除所有容器池中的容器
        async with self.container_pool_lock:
            for container_id in self.container_pool:
                try:
                    subprocess.run(["docker", "stop", container_id], capture_output=True)
                    subprocess.run(["docker", "rm", container_id], capture_output=True)
                except Exception:
                    pass
            self.container_pool = []