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
