# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目简介

这是一个 Python 代码解释器服务，通过 Docker 容器沙箱执行用户提交的 Python 代码，支持数据分析库（pandas、numpy、matplotlib 等）、图片生成和文件输入输出。

## 核心架构

### 三层结构
- **Gateway 层** (`gateway/`): FastAPI 应用入口与路由，处理 HTTP 请求
- **Executor 层** (`executors/`): Docker 容器执行器，负责代码运行与容器池管理
- **Common 层** (`common/`): 通用组件（配置 Settings、协议 Contracts、工具 Utils）

### 执行流程
1. FastAPI 接收 `/api/v1/execute` POST 请求（代码 + 可选的输入文件 URL 列表）
2. `CodeExecutor` 从容器池获取或创建容器
3. 自动检测代码中的 import 语句，按需安装依赖包
4. 下载输入文件到 `/code/input/`，并自动替换代码中的 URL 为容器内路径
5. 在容器内执行代码（超时控制、资源限制）
6. 收集输出（stdout/stderr、matplotlib 图片、`/code/output/` 目录文件）
7. 容器放回池中复用，清理临时文件

### 容器池机制
- 服务启动时预热 `pool_warm_size` 个容器（默认 `min(MAX_WORKERS, 2)`）
- 容器命名格式：`python_exec_pool_{EXECUTOR_INSTANCE_ID}_{index}`
- 支持多实例部署（通过 `EXECUTOR_INSTANCE_ID` 避免命名冲突）
- 后台 keepalive 任务每 60 秒检查并自愈容器池
- 容器复用时自动清理上次执行残留文件

## 常用命令

### 本地开发
```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env

# 启动服务（开发模式，支持热重载）
python main.py
```

### Docker 部署

**构建 API 镜像：**
```bash
docker build -f Dockerfile.api -t python-code-interpreter-api:latest .
```

**单实例运行：**
```bash
docker run --rm -p 14564:14564 \
  -e DOCKER_IMAGE=registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest \
  -e EXECUTOR_INSTANCE_ID=$(hostname) \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/images:/data/images \
  -v $(pwd)/files:/data/files \
  python-code-interpreter-api:latest
```

**Docker Compose（推荐）：**
```bash
# 启动（自动预拉取执行器镜像）
docker compose up -d

# 多实例水平扩展
docker compose up --scale code-interpreter-api=3
```

## 关键配置

所有配置通过环境变量设置（参考 `.env.example`）：

- `MAX_WORKERS`: 最大并发容器数（影响容器池大小）
- `EXECUTION_TIMEOUT`: 单次执行超时（秒）
- `DOCKER_IMAGE`: 执行器镜像地址
- `EXECUTOR_INSTANCE_ID`: 实例 ID（多实例部署必须唯一，默认 `HOSTNAME`）
- `PUBLIC_BASE_URL`: 外网访问地址（如 `https://ci.example.com`），设置后返回绝对 URL
- `IMAGE_STORE_PATH` / `FILE_STORE_PATH`: 图片/文件落盘目录
- `OUTPUT_ALLOWED_EXTENSIONS`: 允许回传的输出文件后缀（默认 `md,csv,txt,json,log`）

## 文件输入输出

**输入文件：**
- 请求参数 `files` 传入完整下载 URL 数组
- 服务自动下载到容器 `/code/input/` 目录
- 代码中的 URL 字符串自动替换为容器内路径
- 响应返回 `inputs` 数组，包含 `local_name`（处理同名文件自动重命名）

**输出文件：**
- 代码中写入 `/code/output/` 目录的文件会自动回传
- 支持的后缀由 `OUTPUT_ALLOWED_EXTENSIONS` 控制
- 响应 `files` 数组返回文件下载链接

**图片输出：**
- Matplotlib 图表自动保存为 `result.png`
- 响应 `image_url` 字段返回图片链接

## API 接口

**执行代码：** `POST /api/v1/execute`
```json
{
  "code": "import pandas as pd\nprint('Hello')",
  "files": ["https://example.com/data.csv"]
}
```

**响应：**
```json
{
  "result": "Hello",
  "error": null,
  "execution_time": 0.5,
  "image_url": "/images/plot_xxx.png",
  "files": [{"filename": "...", "url": "/files/...", "size_bytes": 1024}],
  "inputs": [{"url": "...", "local_name": "data.csv", "local_path": "/code/input/data.csv"}]
}
```

**静态资源：**
- `GET /images/{filename}`: 获取生成的图片
- `GET /files/{filename}`: 获取生成的文件

## 开发注意事项

### 修改执行器逻辑
- 主要代码在 `executors/docker_executor.py`
- 容器池初始化在 `initialize()` / `_ensure_warm_pool()`
- 执行入口是 `execute()` 方法
- 容器复用逻辑在 `_run_in_existing_container()`

### 修改 API 路由
- 路由定义在 `gateway/routes.py`
- 使用 FastAPI Depends 注入 `Settings` / `ExecutionService` / `UtilsClass`
- 新增路由需在 `router` 中注册

### 依赖管理
- API 服务依赖：`requirements.txt`
- 执行器容器依赖：`docker-requirements.txt`（构建执行器镜像时使用）
- 运行时按需安装：`_detect_imports()` 自动检测 import 并在容器中安装

### 安全限制
- 容器资源限制：`--memory=1g --cpus=1 --pids-limit=256`
- 网络隔离：`DOCKER_NETWORK_MODE` 可设为 `none`（但会影响 pip）
- 文件大小/数量限制：通过 ENV 配置
- 输出文件白名单：防止回传可执行文件

### 测试
- 单元测试入口：`test_executor.py`
- 测试时需确保 Docker 可用
- 可通过 `DEBUG=true` 启用热重载模式

## 故障排查

**容器池启动失败：**
- 检查 Docker daemon 是否运行
- 检查 `DOCKER_IMAGE` 镜像是否已拉取
- 查看容器日志：`docker logs python_exec_pool_{instance_id}_0`

**执行超时：**
- 调整 `EXECUTION_TIMEOUT` 环境变量
- 检查代码是否有死循环或长时间阻塞操作

**依赖安装失败：**
- 确保容器网络模式不是 `none`
- 检查 `package_mapping` 字典是否包含包名映射

**多实例命名冲突：**
- 确保每个实例 `EXECUTOR_INSTANCE_ID` 唯一
- 建议使用 `HOSTNAME` 或 Kubernetes Pod 名
