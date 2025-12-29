# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

这是一个基于Docker的Python代码解释器服务，通过FastAPI提供REST API接口，支持在隔离容器中安全执行Python代码，并支持数据分析、可视化等常用库。

## 核心架构

### 容器池机制 (executor.py)

- **预热容器池**: 启动时预创建2个容器并预装常用包(numpy, pandas, matplotlib)，减少代码执行延迟
- **容器复用**: 优先使用池中容器执行代码，执行完毕后放回池中
- **动态包安装**: 通过AST解析检测代码依赖，仅安装缺失的包
- **包名映射**: `package_mapping`字典处理import别名(如`pd`→`pandas`)

### 代码执行流程

1. `main.py` 接收POST请求 → `utils.format_python_code()` 清理代码格式
2. `executor._detect_imports()` 检测依赖包 → 生成安装脚本
3. 优先从容器池获取容器，如无可用则创建新容器
4. matplotlib代码自动添加中文字体配置和图表保存逻辑
5. 执行完成后清理临时文件，容器放回池中

### 异步并发设计

- 使用`ThreadPoolExecutor`处理Docker操作(阻塞IO)
- `asyncio.Semaphore`限制同时运行的容器数量(默认4个)
- FastAPI生命周期管理器在应用启动/关闭时初始化/清理容器池

## 关键配置

### 环境变量 (.env)

- `PORT`: 服务端口(默认14564)
- `MAX_WORKERS`: 最大并发容器数(默认4)
- `EXECUTION_TIMEOUT`: 代码执行超时时间(秒,默认60)
- `DOCKER_IMAGE`: Docker镜像名称
- `IMAGE_STORE_PATH`: 图表保存路径(默认./images)
- `DEBUG`: 是否开启热重载

### Docker镜像

基础镜像已包含完整依赖，见`docker-requirements.txt`，包括：
- 数据分析: numpy, pandas, scipy, scikit-learn
- 可视化: matplotlib, seaborn, plotly
- NLP: nltk, spacy
- 图像处理: Pillow, opencv-python-headless

## 常用命令

### 开发环境

```bash
# 安装依赖
pip install -r requirements.txt

# 启动开发服务器(支持热重载)
DEBUG=true python main.py

# 生产环境启动
python main.py

# 运行测试
python test_executor.py
```

### Docker操作

```bash
# 拉取镜像
docker pull registry.cn-hangzhou.aliyuncs.com/ripper/python-executor:latest

# 构建镜像
docker build -t python-executor:latest .

# 手动清理容器
docker rm -f $(docker ps -a | grep python_exec | awk '{print $1}')
```

## 代码修改注意事项

### 添加新的包映射

在`executor.py:22-38`的`package_mapping`字典中添加映射关系，格式为`'import名': 'pip包名'`

### 修改容器池大小

在`executor._initialize_container_pool()`中调整`pool_size`，注意平衡启动速度和资源占用

### 图表处理逻辑

- matplotlib代码会自动在末尾添加图表保存代码(executor.py:242-248)
- 图表文件名格式: `plot_{execution_id}_{timestamp}.png`
- 中文字体使用WenQuanYi Micro Hei(需在Docker镜像中预装)

### 容器资源限制

在`_run_in_container()`和`_initialize_container_pool()`中通过`--memory`和`--cpus`参数调整

## API接口

### POST /api/v1/execute

执行Python代码

**请求体:**
```json
{
  "code": "print('Hello World')"
}
```

**响应示例:**
```json
{
  "result": "Hello World",
  "error": null,
  "execution_time": 0.45,
  "image_url": "/images/plot_xxx.png"
}
```

### GET /images/{filename}

获取生成的图表图片

## 故障排查

### 容器启动失败
检查Docker镜像是否存在: `docker images | grep python-executor`

### 包安装失败
检查`docker-requirements.txt`中的版本兼容性，或在容器中手动测试安装

### 图表不显示中文
确保Docker镜像包含`fonts-wqy-microhei`字体包(见Dockerfile:22)

### 执行超时
调整`EXECUTION_TIMEOUT`环境变量或优化代码执行效率
