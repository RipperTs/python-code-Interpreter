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

        return list(required_packages)


    async def execute_code(self, code):
        """异步执行代码"""
        async with self.container_semaphore:  # 限制并发容器数量
            execution_id = str(uuid.uuid4())
            start_time = time.time()

            try:
                # 在线程池中准备代码文件
                code_file = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._prepare_code_file,
                    execution_id,
                    code
                )

                # 在线程池中运行容器
                result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._run_in_container,
                    execution_id,
                    code_file
                )

                execution_time = time.time() - start_time

                # 在线程池中清理临时文件
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._cleanup,
                    execution_id
                )

                return {
                    'result': result.get('output', ''),
                    'error': result.get('error', None),
                    'execution_time': execution_time,
                    'image_url': result.get('image_url', None)
                }

            except Exception as e:
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
        if required_packages:
            # 准备安装脚本
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


        # 添加字体设置和图片保存代码
        setup_code = """
import matplotlib.pyplot as plt
import matplotlib as mpl

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False
"""

        detection_code = """
# 保存原始的执行结果
__result = result if 'result' in locals() else None

# 检查是否有图表生成
if plt.get_fignums():
    plt.savefig('/code/output/result.png', dpi=300, bbox_inches='tight')
    plt.close('all')

# 恢复执行结果
result = __result
"""

        # 只有当代码中包含 matplotlib 时才添加设置代码
        if 'plt' in code or 'matplotlib' in code:
            code = setup_code + code + detection_code

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

    def _run_in_container(self, execution_id, code_file):
        """在Docker容器中运行代码"""
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
            "python", "/code/script.py"
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