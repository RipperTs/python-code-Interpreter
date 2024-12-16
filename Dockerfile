FROM registry.cn-hangzhou.aliyuncs.com/ripper/python:3.9-slim

# 设置工作目录
WORKDIR /app

# 安装必要的系统依赖并清理APT缓存
RUN apt-get update && apt-get install -y \
    wget \
    fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

# 升级pip到最新版本
RUN pip install --no-cache-dir --upgrade pip

# 安装Python依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 复制应用程序代码到镜像中
COPY . .

# 暴露端口
EXPOSE 14564

# 运行应用程序
CMD ["python", "main.py"]
