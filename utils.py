import os
import uuid
import logging


class UtilsClass:
    """
    工具类
    """

    def __init__(self, image_dir: str = 'images'):
        # 定义保存图像的目录
        self.image_dir = image_dir
        if not os.path.exists(self.image_dir):
            os.makedirs(self.image_dir)

    def get_image_dir(self) -> str:
        return self.image_dir

    def format_python_code(self, code) -> str:
        """
        去掉```python```代码块标记
        :param code: 代码
        :return:
        """
        if code.startswith('```python'):
            code = code[9:]
        if code.endswith('```'):
            code = code[:-3]

        # 去掉 plt.show() 语句, 避免弹出图表窗口阻塞程序
        code = code.replace('plt.show()', '')
        return code

    def chart_generation(self, plt):
        """
        生成图表
        :param plt: matplotlib.pyplot 对象
        :return: 示例:/images/83283c31a32e4b07a1e739a45bbe7ab6.png
        """
        try:
            # 生成唯一的文件名
            filename = f"{uuid.uuid4().hex}.png"
            filepath = os.path.join(self.image_dir, filename)

            # 将图表保存到文件中
            plt.savefig(filepath, format='png')
            plt.close()

            # 返回图像的URL
            image_url = f"/images/{filename}"
            return image_url
        except Exception as e:
            logging.error(f"Error generating chart: {e}")
            return ""
