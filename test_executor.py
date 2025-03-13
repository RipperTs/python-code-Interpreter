#!/usr/bin/env python3
import asyncio
import os
import time
from executor import CodeExecutor

async def test_executor():
    # 创建执行器
    executor = CodeExecutor()
    
    # 初始化执行器（创建容器池）
    print("正在初始化执行器...")
    await executor.initialize()
    print("执行器初始化完成")
    
    # 测试简单代码
    print("\n测试简单代码执行:")
    simple_code = """
print("Hello, World!")
result = 42
print(f"计算结果: {result}")
"""
    result = await executor.execute_code(simple_code)
    print(f"执行结果: {result}")
    print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
    
    # 测试使用numpy的代码
    print("\n测试使用numpy的代码:")
    numpy_code = """
import numpy as np
arr = np.array([1, 2, 3, 4, 5])
print(f"数组: {arr}")
print(f"数组平均值: {np.mean(arr)}")
"""
    result = await executor.execute_code(numpy_code)
    print(f"执行结果: {result}")
    print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
    
    # 测试使用matplotlib的代码
    print("\n测试使用matplotlib的代码:")
    matplotlib_code = """
import matplotlib.pyplot as plt
import numpy as np

x = np.linspace(0, 10, 100)
y = np.sin(x)

plt.figure(figsize=(8, 4))
plt.plot(x, y, 'r-', label='sin(x)')
plt.title('正弦函数')
plt.xlabel('x')
plt.ylabel('y')
plt.grid(True)
plt.legend()
"""
    result = await executor.execute_code(matplotlib_code)
    print(f"执行结果: {result}")
    print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
    if result.get('image_url'):
        print(f"生成的图像: {result['image_url']}")
    
    # 测试错误代码
    print("\n测试错误代码:")
    error_code = """
# 这是一个会产生错误的代码
x = 10
y = 0
result = x / y  # 除以零错误
"""
    result = await executor.execute_code(error_code)
    print(f"执行结果: {result}")
    print(f"执行时间: {result.get('execution_time', 0):.2f}秒")
    
    # 关闭执行器
    print("\n关闭执行器...")
    await executor.shutdown()
    print("执行器已关闭")

if __name__ == "__main__":
    # 确保图像存储目录存在
    os.makedirs('./images', exist_ok=True)
    
    # 设置环境变量
    os.environ['IMAGE_STORE_PATH'] = './images'
    
    # 运行测试
    asyncio.run(test_executor()) 