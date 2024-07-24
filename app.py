from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_file
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import traceback
import os
import resource
import time
import logging

from utils import UtilsClass

app = Flask(__name__)
load_dotenv()
utils = UtilsClass()

# 设置资源限制
MAX_EXECUTION_TIME = 10  # 最大执行时间（秒）
MAX_MEMORY_USAGE = 1024 * 1024 * 1024  # 最大内存使用量（字节）

# 设置华文宋体字体
font_path = os.environ.get('FONT_PATH', '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc')
font_prop = fm.FontProperties(fname=font_path)
plt.rcParams['font.family'] = font_prop.get_name()

plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题


def limit_resources():
    resource.setrlimit(resource.RLIMIT_CPU, (MAX_EXECUTION_TIME, MAX_EXECUTION_TIME))
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_USAGE, MAX_MEMORY_USAGE))


@app.route('/api/v1/execute', methods=['POST'])
def execute():
    try:
        # 从请求中获取代码
        code = request.json.get('code', '')
        if not code:
            return jsonify({'error': 'No code provided.'}), 400

        # 格式化代码, 将其优化为可执行的代码
        code = utils.format_python_code(code)

        # 定义一个字典来存储执行环境
        exec_env = {'pd': pd, 'plt': plt}

        # 执行代码，并限制资源使用
        start_time = time.time()
        exec_locals = {}
        exec(code, exec_env, exec_locals)
        execution_time = time.time() - start_time

        # 获取执行结果
        result = exec_locals.get('result', 'No result variable defined.')
        if result == 'No result variable defined.':
            # 如果没有定义 result 变量，尝试获取最后一个变量
            result = exec_locals.get(list(exec_locals.keys())[-1], 'No result variable defined.')

        # 检查是否有图表生成
        if plt.gcf().get_axes():
            image_url = utils.chart_generation(plt)
            return jsonify({'result': str(result), 'image_url': image_url, 'execution_time': execution_time})

        return jsonify({'result': str(result), 'execution_time': execution_time})
    except Exception as e:
        return jsonify({'error': str(e), 'traceback': traceback.format_exc()})


@app.route('/images/<filename>', methods=['GET'])
def get_image(filename):
    try:
        path_or_file = os.path.join(utils.get_image_dir(), filename)
        return send_file(path_or_file, mimetype='image/png')
    except FileNotFoundError:
        return jsonify({'error': 'File not found'}), 404


if __name__ == '__main__':
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    port = int(os.environ.get('PORT', 14564))
    app.run(host='0.0.0.0', port=port, debug=debug)
