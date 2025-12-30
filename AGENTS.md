# Repository Guidelines

## 项目结构与模块组织

- `gateway/`：FastAPI 网关（`app.py` 组装应用，`routes.py` 提供接口路由）
- `executors/`：执行器实现（Docker 执行、容器池、超时与并发控制）
- `common/`：通用组件（`settings.py`/`contracts.py`/`utils.py`）
- `main.py`：本地启动入口（保持 `python main.py` 可用）
- `images/`、`files/`：图片/文件落盘目录（开发调试或部署时挂载）
- `Dockerfile`（执行器镜像）、`Dockerfile.api`（API 镜像）、`docker-compose.yml`（多实例编排）

## 构建、测试与开发命令

- 创建虚拟环境：`python3 -m venv .venv && source .venv/bin/activate`
- 安装依赖：`pip install -r requirements.txt`
- 初始化配置：`cp .env.example .env`
- 本地运行 API：`python main.py`（端口/镜像等由 `.env` 控制）
- 集成测试：`python test_executor.py`（需要本机 Docker daemon 可用）
- 构建镜像：`./build_image.sh` 或 `docker build -f Dockerfile.api -t <tag> .`
- 多实例运行：`docker compose up --build --scale api=3`

## 编码风格与命名约定

- Python：遵循 PEP 8、4 空格缩进；函数/变量用 `snake_case`，类用 `PascalCase`
- 分层：接口层尽量薄（`gateway/` 只做参数/错误处理），执行逻辑集中在 `executors/`
- 新增/修改环境变量：必须同步更新 `.env.example` 与 `README.md`
- 不提交敏感与生成物：`.env`、密钥、`__pycache__/`、`images/`/`files/` 下的产物

## 测试指南

- 当前以集成测试为主：覆盖成功输出、异常返回、`image_url`/`files` 回传
- 需要新增单测时：建议新增 `tests/` 并使用标准库 `unittest`（避免引入新依赖）

## 与 AI 协作约定

- 除非用户明确要求：不补充/新增测试用例，不做本地启动与验证（只给出建议自测命令与步骤）

## 提交与 Pull Request 指南

- Commit 信息：保持简短清晰，常见格式为“中文动词开头 + 变更点”（如“新增/优化/更新/重构 …”）
- PR 需包含：变更目的、影响的接口/ENV、关键配置变更、最少一条自测命令与结果

## 安全与配置提示

- 生产部署 API 镜像通常需要挂载 Docker Socket：`-v /var/run/docker.sock:/var/run/docker.sock`
- 可通过 `DOCKER_NETWORK_MODE=none` 收紧执行容器网络；输出文件受 `OUTPUT_ALLOWED_EXTENSIONS` 等限额控制
