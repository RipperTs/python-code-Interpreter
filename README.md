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