import subprocess
import uuid
import time
import os
import ast
import re
import shutil
import json
from concurrent.futures import ThreadPoolExecutor
import asyncio

from execution_service import ExecuteRequest, ExecuteResult, OutputFile
from settings import Settings


class CodeExecutor:
    """
    代码执行器
    """
    def __init__(self, settings: Settings = None):
        self.settings = settings or Settings.from_env()
        self.max_workers = max(1, int(self.settings.max_workers))
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.timeout = self.settings.execution_timeout
        self.docker_image = self.settings.docker_image
        # 用于限制同时运行的容器数量
        self.container_semaphore = asyncio.Semaphore(self.max_workers)
        self.pool_warm_size = max(1, min(self.max_workers, 2))
        self.pool_container_prefix = "python_exec_pool_"
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
        self.in_use_pool_containers = set()
        self.keepalive_interval_seconds = 60
        self.keepalive_task = None
        self.keepalive_stop_event = asyncio.Event()
        # 容器池初始化标志
        self.pool_initialized = False
        
    async def initialize(self):
        """异步初始化方法，用于初始化容器池"""
        if self.pool_initialized:
            return

        await self._ensure_warm_pool()
        self.pool_initialized = True

        if self.keepalive_task is None or self.keepalive_task.done():
            self.keepalive_stop_event.clear()
            self.keepalive_task = asyncio.create_task(self._keepalive_loop())
        
    async def _initialize_container_pool(self):
        """初始化容器池，预先创建一些容器"""
        await self._ensure_warm_pool()

    async def _run_docker(self, *cmd: str):
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode(errors="replace"), stderr.decode(errors="replace")

    def _sanitize_filename(self, name: str) -> str:
        name = os.path.basename(name or "")
        if not name or name in {".", ".."}:
            return ""
        return name

    def _is_allowed_output_file(self, name: str) -> bool:
        if not name or name == "result.png":
            return False
        _, ext = os.path.splitext(name)
        ext = ext.lower().lstrip(".")
        allowed = self.settings.output_allowed_extensions or set()
        return ext in allowed

    def _persist_output_files(self, execution_id: str, output_dir: str) -> list[OutputFile]:
        os.makedirs(self.settings.file_store_path, exist_ok=True)

        try:
            names = sorted(os.listdir(output_dir))
        except FileNotFoundError:
            return []

        results: list[OutputFile] = []
        total_bytes = 0
        index = 0
        for name in names:
            if len(results) >= self.settings.output_max_files:
                break
            safe_name = self._sanitize_filename(name)
            if safe_name != name:
                continue
            if not self._is_allowed_output_file(safe_name):
                continue

            src_path = os.path.join(output_dir, safe_name)
            if not os.path.isfile(src_path):
                continue

            size_bytes = int(os.path.getsize(src_path))
            if size_bytes <= 0:
                continue
            if size_bytes > self.settings.output_file_max_bytes:
                continue
            if total_bytes + size_bytes > self.settings.output_total_max_bytes:
                break

            index += 1
            stored_name = f"out_{execution_id}_{index}_{safe_name}"
            dst_path = os.path.join(self.settings.file_store_path, stored_name)
            shutil.move(src_path, dst_path)
            os.chmod(dst_path, 0o666)

            results.append(
                OutputFile(
                    filename=stored_name,
                    original_name=safe_name,
                    size_bytes=size_bytes,
                )
            )
            total_bytes += size_bytes

        return results

    def _pool_container_names(self):
        return [f"{self.pool_container_prefix}{i}" for i in range(self.pool_warm_size)]

    async def _is_container_running(self, container_id: str):
        rc, stdout, _stderr = await self._run_docker(
            "docker", "inspect", "-f", "{{.State.Running}}", container_id
        )
        if rc != 0:
            return None
        return stdout.strip().lower() == "true"

    async def _remove_container(self, container_id: str):
        await self._run_docker("docker", "rm", "-f", container_id)

    def _docker_run_base_args(self):
        args = [
            "--init",
            "--network", self.settings.docker_network_mode,
            "--memory=1g",
            "--cpus=1",
            "--pids-limit", str(self.settings.docker_pids_limit),
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
        ]
        return args

    async def _create_pool_container(self, container_id: str):
        cmd = [
            "docker", "run",
            "-d",  # 后台运行
            "--name", container_id,
            "--restart", "unless-stopped",
            *self._docker_run_base_args(),
            self.docker_image,
            "tail", "-f", "/dev/null"  # 保持容器运行
        ]
        rc, _stdout, stderr = await self._run_docker(*cmd)
        if rc == 0:
            await self._preinstall_common_packages(container_id)
            return True

        # 容器名冲突：复用已有容器（若存在/可用），否则删除后重建
        if "is already in use" in stderr or "Conflict" in stderr:
            running = await self._is_container_running(container_id)
            if running is True:
                return True
            await self._remove_container(container_id)
            rc, _stdout, _stderr = await self._run_docker(*cmd)
            if rc == 0:
                await self._preinstall_common_packages(container_id)
                return True
        return False

    async def _ensure_warm_pool(self):
        """确保至少有 pool_warm_size 个池容器在线（自愈 + 复用已有容器）"""
        desired = self._pool_container_names()

        for container_id in desired:
            try:
                running = await self._is_container_running(container_id)
                if running is True:
                    continue
                if running is False:
                    await self._remove_container(container_id)
                await self._create_pool_container(container_id)
            except Exception:
                # Docker 不可用或临时异常时，避免阻塞服务
                continue

        async with self.container_pool_lock:
            self.container_pool = [
                cid for cid in desired if cid not in self.in_use_pool_containers
            ]

    async def _keepalive_loop(self):
        while not self.keepalive_stop_event.is_set():
            try:
                await self._ensure_warm_pool()
            except Exception:
                pass
            try:
                await asyncio.wait_for(
                    self.keepalive_stop_event.wait(),
                    timeout=self.keepalive_interval_seconds,
                )
            except asyncio.TimeoutError:
                continue

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

        return list(required_packages)

    async def execute(self, request: ExecuteRequest) -> ExecuteResult:
        """执行代码（与 HTTP / FastAPI 解耦的领域接口）"""
        # 确保容器池已初始化
        if not self.pool_initialized:
            await self.initialize()

        async with self.container_semaphore:  # 限制并发容器数量
            execution_id = str(uuid.uuid4())
            start_time = time.time()
            container_id = None

            try:
                # 尝试从容器池获取容器
                await self._ensure_warm_pool()
                async with self.container_pool_lock:
                    if self.container_pool:
                        container_id = self.container_pool.pop(0)
                        self.in_use_pool_containers.add(container_id)

                # 在线程池中准备代码文件
                code_file = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._prepare_code_file,
                    execution_id,
                    request.code
                )

                # 在线程池中运行代码
                run_result = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._run_code,
                    execution_id,
                    code_file,
                    container_id
                )

                execution_time = time.time() - start_time

                output_dir = f"/tmp/python_executor/{execution_id}/output"
                files = await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._persist_output_files,
                    execution_id,
                    output_dir
                )

                # 在线程池中清理临时文件
                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._cleanup,
                    execution_id
                )

                # 如果使用了池中的容器，将其放回池中
                if container_id and container_id.startswith(self.pool_container_prefix):
                    async with self.container_pool_lock:
                        self.in_use_pool_containers.discard(container_id)
                        if container_id not in self.container_pool:
                            self.container_pool.append(container_id)

                return ExecuteResult(
                    stdout=run_result.get("output", "") or "",
                    stderr=run_result.get("error", None),
                    execution_time=execution_time,
                    image_filename=run_result.get("image_filename"),
                    files=files,
                )

            except Exception as e:
                # 如果使用了池中的容器，将其放回池中
                if container_id and container_id.startswith(self.pool_container_prefix):
                    async with self.container_pool_lock:
                        self.in_use_pool_containers.discard(container_id)
                        if container_id not in self.container_pool:
                            self.container_pool.append(container_id)

                await asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    self._cleanup,
                    execution_id
                )
                return ExecuteResult(
                    stdout="",
                    stderr=str(e),
                    execution_time=time.time() - start_time,
                    image_filename=None,
                    files=[],
                )

    async def execute_code(self, code):
        """异步执行代码（兼容旧接口：返回 dict）"""
        exec_result = await self.execute(ExecuteRequest(code=code))
        return exec_result.to_legacy_dict(
            image_url_prefix=self.settings.image_url_prefix,
            file_url_prefix=self.settings.file_url_prefix,
        )

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
from importlib import metadata

def install_package(package):
    try:
        metadata.version(package)
        return
    except metadata.PackageNotFoundError:
        pass

    process = subprocess.run(
        [sys.executable, '-m', 'pip', 'install', '--user', '--no-input', package],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        raise RuntimeError(
            (process.stderr or process.stdout or f"pip install failed: {package}").strip()
        )

"""
            # 添加包安装代码
            for package in required_packages:
                setup_code += f"install_package('{package}')\n"

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
            
            # 准备输出目录（清空旧产物）
            prepare_output_cmd = [
                "docker", "exec", container_id,
                "bash", "-c",
                "mkdir -p /code/output && rm -rf /code/output/*"
            ]
            subprocess.run(prepare_output_cmd, check=True, capture_output=True)
            
            # 执行代码
            exec_cmd = [
                "docker", "exec", container_id,
                "bash", "-c",
                (
                    f"if command -v timeout >/dev/null 2>&1; then "
                    f"timeout -k 2s {self.timeout}s python /code/script.py; "
                    f"else python /code/script.py; fi"
                )
            ]
            process = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout + 5
            )
            
            result = {
                'output': process.stdout.strip(),
                'error': process.stderr if process.returncode != 0 else None,
            }
            
            # 处理图片输出
            image_path = os.path.join(output_dir, "result.png")
            has_image_cmd = [
                "docker", "exec", container_id,
                "bash", "-c",
                "test -f /code/output/result.png"
            ]
            has_image = subprocess.run(has_image_cmd, capture_output=True).returncode == 0
            if has_image:
                copy_image_cmd = [
                    "docker", "cp",
                    f"{container_id}:/code/output/result.png",
                    image_path,
                ]
                subprocess.run(copy_image_cmd, check=True, capture_output=True)

                timestamp = int(time.time())
                image_filename = f"plot_{execution_id}_{timestamp}.png"
                permanent_path = os.path.join(
                    self.settings.image_store_path,
                    image_filename
                )
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                shutil.move(image_path, permanent_path)
                os.chmod(permanent_path, 0o666)
                result["image_filename"] = image_filename

            container_list_cmd = [
                "docker", "exec", container_id,
                "python", "-c",
                (
                    "import os, json\n"
                    "p='/code/output'\n"
                    "items=[]\n"
                    "for n in os.listdir(p):\n"
                    "    fp=os.path.join(p,n)\n"
                    "    if os.path.isfile(fp):\n"
                    "        items.append({'name': n, 'size': os.path.getsize(fp)})\n"
                    "print(json.dumps(items, ensure_ascii=False))\n"
                ),
            ]
            listed = subprocess.run(container_list_cmd, capture_output=True, text=True)
            if listed.returncode == 0 and listed.stdout.strip():
                try:
                    items = json.loads(listed.stdout.strip())
                except Exception:
                    items = []

                for item in items:
                    name = self._sanitize_filename(str(item.get("name", "")))
                    if not self._is_allowed_output_file(name):
                        continue
                    dst_path = os.path.join(output_dir, name)
                    copy_cmd = ["docker", "cp", f"{container_id}:/code/output/{name}", dst_path]
                    subprocess.run(copy_cmd, check=False, capture_output=True)
                
            # 清理容器中的临时文件
            cleanup_cmd = ["docker", "exec", container_id, "rm", "-f", "/code/script.py"]
            subprocess.run(cleanup_cmd, capture_output=True)
            cleanup_output_cmd = [
                "docker", "exec", container_id,
                "bash", "-c",
                "rm -rf /code/output/*"
            ]
            subprocess.run(cleanup_output_cmd, capture_output=True)
            
            return result
            
        except subprocess.TimeoutExpired:
            # 超时兜底：尽力清理本次脚本与输出
            subprocess.run(
                ["docker", "exec", container_id, "pkill", "-f", "/code/script.py"],
                capture_output=True
            )
            subprocess.run(
                ["docker", "exec", container_id, "bash", "-c", "rm -rf /code/output/* /code/script.py"],
                capture_output=True
            )
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
            *self._docker_run_base_args(),
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
                    self.settings.image_store_path,
                    image_filename
                )
                os.makedirs(os.path.dirname(permanent_path), exist_ok=True)
                shutil.move(image_path, permanent_path)
                os.chmod(permanent_path, 0o666)
                result["image_filename"] = image_filename

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
        self.keepalive_stop_event.set()
        if self.keepalive_task:
            self.keepalive_task.cancel()
            try:
                await self.keepalive_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        # 关闭线程池
        self.executor.shutdown(wait=True)
        
        # 停止并删除所有容器池中的容器
        container_ids = set(self._pool_container_names())
        async with self.container_pool_lock:
            container_ids.update(self.container_pool)
            container_ids.update(self.in_use_pool_containers)
            self.container_pool = []
            self.in_use_pool_containers = set()

        for container_id in container_ids:
            if not container_id.startswith(self.pool_container_prefix):
                continue
            try:
                subprocess.run(["docker", "stop", container_id], capture_output=True)
                subprocess.run(["docker", "rm", container_id], capture_output=True)
            except Exception:
                pass
