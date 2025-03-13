#!/bin/bash

# 设置变量
IMAGE_NAME="registry.cn-hangzhou.aliyuncs.com/ripper/python-executor"
TAG="latest"
FULL_IMAGE_NAME="${IMAGE_NAME}:${TAG}"

# 显示构建信息
echo "开始构建 ${FULL_IMAGE_NAME} 镜像..."

# 构建Docker镜像
docker build -t ${FULL_IMAGE_NAME} .

# 检查构建是否成功
if [ $? -eq 0 ]; then
    echo "镜像构建成功: ${FULL_IMAGE_NAME}"
    
    # 显示镜像信息
    echo "镜像详情:"
    docker images ${FULL_IMAGE_NAME}
    
    # 询问是否要推送到远程仓库
    read -p "是否要推送镜像到远程仓库? (y/n): " PUSH_IMAGE
    
    if [ "$PUSH_IMAGE" = "y" ] || [ "$PUSH_IMAGE" = "Y" ]; then
        # 询问远程仓库地址
        read -p "请输入远程仓库地址 (例如: registry.cn-hangzhou.aliyuncs.com/ripper/python-executor): " REGISTRY
        
        if [ -n "$REGISTRY" ]; then
            # 标记镜像
            REMOTE_IMAGE="${REGISTRY}/${IMAGE_NAME}:${TAG}"
            docker tag ${FULL_IMAGE_NAME} ${REMOTE_IMAGE}
            
            # 推送镜像
            echo "推送镜像到 ${REMOTE_IMAGE}..."
            docker push ${REMOTE_IMAGE}
            
            if [ $? -eq 0 ]; then
                echo "镜像推送成功: ${REMOTE_IMAGE}"
            else
                echo "镜像推送失败"
                exit 1
            fi
        else
            echo "未提供远程仓库地址，跳过推送"
        fi
    else
        echo "跳过推送镜像"
    fi
    
    # 询问是否要更新executor.py中的镜像名称
    read -p "是否要更新executor.py中的镜像名称? (y/n): " UPDATE_EXECUTOR
    
    if [ "$UPDATE_EXECUTOR" = "y" ] || [ "$UPDATE_EXECUTOR" = "Y" ]; then
        if [ -n "$REGISTRY" ]; then
            # 更新executor.py中的镜像名称
            sed -i '' "s|self.docker_image = os.environ.get('DOCKER_IMAGE', '.*')|self.docker_image = os.environ.get('DOCKER_IMAGE', '${REGISTRY}/${IMAGE_NAME}:${TAG}')|g" executor.py
            echo "已更新executor.py中的镜像名称为: ${REGISTRY}/${IMAGE_NAME}:${TAG}"
        else
            # 更新executor.py中的镜像名称为本地镜像
            sed -i '' "s|self.docker_image = os.environ.get('DOCKER_IMAGE', '.*')|self.docker_image = os.environ.get('DOCKER_IMAGE', '${FULL_IMAGE_NAME}')|g" executor.py
            echo "已更新executor.py中的镜像名称为: ${FULL_IMAGE_NAME}"
        fi
    fi
    
    echo "构建过程完成"
else
    echo "镜像构建失败"
    exit 1
fi 