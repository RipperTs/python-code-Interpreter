# Code解释器

> 一个简单的代码解释器，支持解释Python代码, 支持 pandas, numpy, matplotlib, seaborn, scikit-learn等库


## 运行

**1. 拉取Code解释器镜像**  
```bash
docker registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest
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

## 使用
在线接口文档: https://apifox.com/apidoc/shared-1dd2957c-1f9e-4179-80a3-c6e16790feeb

## 配置（ENV）
- `IMAGE_STORE_PATH`：生成图片的落盘目录（默认 `./images`）
- `IMAGE_URL_PREFIX`：接口返回的图片 URL 前缀（默认 `/images`）
- `DOCKER_NETWORK_MODE`：容器网络模式（默认 `bridge`；更严格可设 `none`）
- `DOCKER_PIDS_LIMIT`：容器最大进程数限制（默认 `256`）

## 执行器说明
- 服务启动后会预热并保活容器池（默认至少 1 个 `python_exec_pool_0`），长时间空闲也会自动自愈

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
