# Code解释器

> 一个简单的代码解释器，支持解释Python代码, 支持 pandas, numpy, matplotlib, seaborn, scikit-learn等库

## 目录结构
- `gateway/`：FastAPI 网关（路由、应用组装）
- `executors/`：执行器实现（Docker 执行与容器池）
- `common/`：通用组件（配置、协议、工具）
- `main.py`：应用入口（保持 `python main.py` 可用）
- `Dockerfile`：执行器镜像
- `Dockerfile.api`：API 镜像

## 运行

**1. 拉取Code解释器镜像**  
```bash
docker pull registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest
```

**2. 克隆仓库**   
```bash
git clone https://github.com/RipperTs/python-code-Interpreter.git
```

**3. 配置ENV文件**   
```bash
cp .env.example .env
```

**4. 安装依赖**     
```bash
pip install -r requirements.txt
```

**5. 运行**     
```bash
python main.py
```

## Docker 部署（推荐）
建议把 API 服务打成镜像运行，执行器镜像通过 `DOCKER_IMAGE` 配置；API 容器需挂载宿主机 Docker Socket（用于创建执行容器）。

**1. 构建 API 镜像**
```bash
docker build -f Dockerfile.api -t python-code-interpreter-api:latest .
```

**2. 运行 API（单实例）**
```bash
docker run --rm -p 14564:14564 \
  -e DOCKER_IMAGE=registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest \
  -e EXECUTOR_INSTANCE_ID=$(hostname) \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v $(pwd)/images:/data/images \
  -v $(pwd)/files:/data/files \
  -e IMAGE_STORE_PATH=/data/images \
  -e FILE_STORE_PATH=/data/files \
  python-code-interpreter-api:latest
```

**3. 多实例（水平扩展）**
```bash
docker compose up --build --scale api=3
```
多实例时务必保证每个实例 `EXECUTOR_INSTANCE_ID` 唯一（默认用容器 `HOSTNAME` 即可），避免池容器命名冲突。

## docker-compose 运行（远程镜像）
`docker-compose.yml` 默认直接使用远程 API 镜像，并会在启动 API 前预拉取执行器镜像，降低首次执行卡顿。
```bash
docker compose up -d
```

## 使用
在线接口文档: https://apifox.com/apidoc/shared-1dd2957c-1f9e-4179-80a3-c6e16790feeb

## 配置（ENV）
- `DOCKER_IMAGE`：执行器镜像（默认 `registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest`）
- `MAX_WORKERS`：最大并发（同时运行容器数）
- `EXECUTION_TIMEOUT`：单次执行超时（秒）
- `EXECUTOR_INSTANCE_ID`：实例 ID（多实例部署时用于避免池容器命名冲突；默认用 `HOSTNAME`）
- `PUBLIC_BASE_URL`：对外访问地址（如 `https://ci.example.com`），设置后 `image_url/files[].url` 返回可直接点击的绝对链接
- `IMAGE_STORE_PATH`：生成图片的落盘目录（默认 `./images`）
- `IMAGE_URL_PREFIX`：接口返回的图片 URL 前缀（默认 `/images`）
- `FILE_STORE_PATH`：生成文件的落盘目录（默认 `./files`）
- `FILE_URL_PREFIX`：接口返回的文件 URL 前缀（默认 `/files`）
- `DOCKER_NETWORK_MODE`：容器网络模式（默认 `bridge`；更严格可设 `none`）
- `DOCKER_PIDS_LIMIT`：容器最大进程数限制（默认 `256`）
- `OUTPUT_ALLOWED_EXTENSIONS`：允许回传的输出文件后缀白名单（默认 `md,csv,txt,json,log`）
- `OUTPUT_MAX_FILES/OUTPUT_FILE_MAX_BYTES/OUTPUT_TOTAL_MAX_BYTES`：输出文件数量/大小限额
- `INPUT_MAX_FILES/INPUT_FILE_MAX_BYTES/INPUT_TOTAL_MAX_BYTES`：输入文件数量/大小限额

## 执行器说明
- 服务启动后会预热并保活容器池（默认至少 1 个 `python_exec_pool_<EXECUTOR_INSTANCE_ID>_0`），长时间空闲也会自动自愈

## 文件输出
- 在代码里把文件写到容器目录 `/code/output/`，接口会把常见文件（如 `md/csv/txt/json`）落盘并在返回值的 `files` 字段里给出下载链接
- 示例：`open('/code/output/result.md','w').write('# Hello')`

## 文件输入
- 请求 `POST /api/v1/execute` 可传 `files`（字符串数组，元素为完整下载地址），服务会先下载到容器目录 `/code/input/`
- 如果你的代码里直接使用了下载地址字符串，服务会自动把它替换成容器内路径（`/code/input/<filename>`）
- 建议写法：`pd.read_csv('/code/input/data.csv')` 或直接 `pd.read_csv('data.csv')`（有文件输入时会在 `/code/input` 目录执行）
- 响应会返回 `inputs` 映射；若出现同名文件，会自动重命名（如 `2_data.csv`），可用 `inputs[*].local_name` 精确引用

#### 查看字体
```bash
# 安装字体包
sudo apt-get update
sudo apt-get install fonts-wqy-zenhei

# 查找字体路径, 示例:/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
fc-list :lang=zh
```

#### 内置库
查看内置库: [docker-requirements.txt](docker-requirements.txt)
