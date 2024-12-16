from flask import Flask, request, jsonify, send_file
import os
from dotenv import load_dotenv
import logging
from executor import CodeExecutor
from utils import UtilsClass

app = Flask(__name__)
load_dotenv()
utils = UtilsClass()
executor = CodeExecutor()


@app.route('/api/v1/execute', methods=['POST'])
def execute():
    try:
        code = request.json.get('code', '')
        if not code:
            return jsonify({'error': 'No code provided.'}), 400

        # 格式化代码
        code = utils.format_python_code(code)

        # 执行代码
        result = executor.execute_code(code)

        if result.get('error'):
            return jsonify(result), 400

        return jsonify(result)

    except Exception as e:
        logging.error(f"Error executing code: {str(e)}")
        return jsonify({'error': str(e)}), 500


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