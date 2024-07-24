# Code解释器

> 一个简单的代码解释器，支持解释Python代码, 支持 pandas, numpy, matplotlib, seaborn, scikit-learn等库


## 如何运行

#### 使用Docker运行
```bash
# Docker
docker-compose up -d
```

#### 打包最新代码并运行
```bash
# 构建最新的Docker镜像
docker-compose build

# 后台运行容器
docker-compose up -d
```

#### 查看字体
```bash
# 安装字体包
sudo apt-get update
sudo apt-get install fonts-wqy-zenhei

# 查找字体路径, 示例:/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc
fc-list :lang=zh
```

