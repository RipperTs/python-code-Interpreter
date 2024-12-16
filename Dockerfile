FROM registry.cn-hangzhou.aliyuncs.com/ripper/python:3.9-slim

# 安装必要的系统依赖和中文字体
RUN apt-get update && apt-get install -y \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装Python依赖
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 创建工作目录
WORKDIR /code

# 创建目录并设置权限
RUN mkdir -p /code/output && \
    chmod -R 777 /code && \
    chmod -R 777 /code/output

# 设置matplotlib后端为Agg（无需显示设备）
ENV MPLBACKEND=Agg

# 创建非root用户
RUN useradd -m -r coderunner
RUN chown -R coderunner:coderunner /code
RUN mkdir -p /home/coderunner/.local && chown -R coderunner:coderunner /home/coderunner

# 切换到非root用户
USER coderunner

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib
ENV PATH="/home/coderunner/.local/bin:${PATH}"