FROM registry.cn-hangzhou.aliyuncs.com/ripper/python:3.9-slim

LABEL maintainer="Python Code Interpreter"
LABEL description="Optimized Python execution environment with pre-installed packages"

# 设置工作目录
WORKDIR /code

# 设置环境变量
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libssl-dev \
    git \
    wget \
    fonts-wqy-microhei \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 安装常用Python包
COPY docker-requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r docker-requirements.txt && \
    # 清理pip缓存
    rm -rf /root/.cache/pip

# 设置matplotlib后端为Agg（无需GUI）
RUN mkdir -p /root/.config/matplotlib && \
    echo "backend: Agg" > /root/.config/matplotlib/matplotlibrc

# 创建输出目录
RUN mkdir -p /code/output

# 设置默认命令
CMD ["python"]