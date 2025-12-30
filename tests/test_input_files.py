import os
import shutil
import unittest
from unittest.mock import patch
from typing import Dict, Optional

from executors.docker_executor import CodeExecutor
from common.settings import Settings


class _FakeResponse:
    def __init__(
        self,
        content: bytes,
        headers: Optional[Dict[str, str]] = None,
        status_code: int = 200,
    ):
        self.status_code = status_code
        self.headers = headers or {}
        self._content = content

    def iter_content(self, chunk_size: int = 1024 * 1024):
        yield self._content

    def close(self):
        return None


class DownloadInputFilesTests(unittest.TestCase):
    def setUp(self):
        self.executor = CodeExecutor(Settings())

    def tearDown(self):
        shutil.rmtree("/tmp/python_executor/unittest", ignore_errors=True)

    @patch("requests.get")
    def test_download_uses_filename_query_param(self, mock_get):
        url = (
            "http://example.com/api/common/file/read"
            "?filename=%E5%B7%A5%E4%BD%9C%E7%B0%BF1_%E5%89%AF%E6%9C%AC.csv&token=xxx"
        )
        mock_get.return_value = _FakeResponse(
            b"sale\n100\n",
            headers={"Content-Disposition": 'attachment; filename="wrong.txt"'},
        )

        input_dir, url_map, inputs = self.executor._download_input_files("unittest", [url])

        self.assertTrue(os.path.isfile(os.path.join(input_dir, "工作簿1_副本.csv")))
        self.assertEqual(url_map[url], "/code/input/工作簿1_副本.csv")
        self.assertEqual(inputs[0].local_name, "工作簿1_副本.csv")
        self.assertEqual(inputs[0].original_name, "工作簿1_副本.csv")

    @patch("requests.get")
    def test_download_uses_content_disposition_when_no_query_name(self, mock_get):
        url = "http://example.com/download"
        mock_get.return_value = _FakeResponse(
            b"sale\n100\n",
            headers={"Content-Disposition": 'attachment; filename="data.csv"'},
        )

        input_dir, url_map, inputs = self.executor._download_input_files("unittest", [url])

        self.assertTrue(os.path.isfile(os.path.join(input_dir, "data.csv")))
        self.assertEqual(url_map[url], "/code/input/data.csv")
        self.assertEqual(inputs[0].local_name, "data.csv")
        self.assertEqual(inputs[0].original_name, "data.csv")


if __name__ == "__main__":
    unittest.main()
