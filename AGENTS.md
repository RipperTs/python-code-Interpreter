# Repository Guidelines

本仓库提供基于 FastAPI + Docker 的 Python 代码执行服务：隔离运行用户代码、自动探测并安装常见依赖、支持返回 `matplotlib` 生成的图片。

## 项目结构与模块组织
- `main.py`：FastAPI 接口与应用生命周期（`POST /api/v1/execute`、`GET /images/{filename}`）
- `executor.py`：核心执行器（容器池、依赖探测/安装、并发与超时控制）
- `utils.py`：工具方法（代码格式化、图片目录等）
- `images/`：本地图片输出目录（开发/调试）
- `Dockerfile` / `docker-requirements.txt`：执行镜像与内置依赖
- `test_executor.py`：集成测试脚本（需要本机 Docker）

## 构建、测试与开发命令
- 环境准备（推荐 `.venv`）：
  - `python3 -m venv .venv && source .venv/bin/activate`
  - `pip install -r requirements.txt`
  - `cp .env.example .env`
- 本地运行 API：`python main.py`（默认端口 `14564`，由 `.env` 的 `PORT` 控制）
- 运行集成测试：`python test_executor.py`
- 构建执行镜像：`./build_image.sh` 或 `docker build -t <image>:<tag> .`
- 拉取预构建镜像（可选）：`docker pull registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest`

## 配置（ENV）
- `DEBUG`：`true/false`，开启后 `uvicorn` 使用 `reload`
- `PORT`：API 监听端口
- `DOCKER_IMAGE`：执行容器镜像名（需本机可拉取 / 可用）
- `MAX_WORKERS`：最大并发容器数（也用于预热容器池）
- `EXECUTION_TIMEOUT`：单次执行超时（秒）
- `IMAGE_STORE_PATH`：图片落盘目录（默认 `./images`，建议确保可写）

## 代码风格与命名约定
- 遵循 PEP 8，4 空格缩进；函数/变量用 `snake_case`，类用 `PascalCase`
- 业务逻辑优先放在 `executor.py`；接口层（`main.py`）保持薄、只做参数/错误处理
- 新增或修改环境变量时，同步更新 `.env.example` 与 `README.md`

## 测试规范
- 修改执行逻辑后至少跑一遍 `test_executor.py`，覆盖：成功输出、异常返回、绘图生成 `image_url`
- 如需新增单元测试，建议新增 `tests/` 并使用标准库 `unittest`（避免引入新依赖）

## 开发注意事项
- 运行与测试依赖本机 Docker daemon，需确保 `docker run` / `docker exec` 可用
- 调整临时目录（`/tmp/python_executor/<execution_id>`）或权限策略时，注意 macOS 与 Linux 行为差异
- 避免引入新的重量级依赖；优先标准库 + `requirements.txt` 既有依赖
- 提交前建议自检：`python -m compileall .`、`python -m pip check`

## 提交与 Pull Request
- 历史提交多为简短描述（中文为主，偶尔带 emoji），建议保持：一句话说明“做了什么/为什么”
  - 示例：`🔧 修复：处理超时返回`、`优化 Dockerfile 缓存层`
- PR 需包含：变更目的、影响的接口/ENV、自测命令；涉及 API 行为变更请同步更新 `README.md`

## 安全与配置提示
- 禁止提交 `.env`、密钥或私有镜像地址；仅提交 `.env.example`
- 执行依赖 Docker 做隔离；修改容器参数（网络/权限/挂载）需在 PR 中说明风险与回滚方式
