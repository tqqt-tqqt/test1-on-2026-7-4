"""输出管理测试。"""

import unittest
import tempfile
import shutil
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xhs_generator.output.file_manager import (
    get_output_dir,
    save_copy,
    save_snapshot,
    save_summary,
)


class TestFileManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = self.temp_dir / "test_output"

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_get_output_dir(self):
        d = get_output_dir(str(self.output_dir), "2026-07-06")
        self.assertEqual(d, self.output_dir / "2026-07-06")

    def test_save_and_read_copy(self):
        d = get_output_dir(str(self.output_dir), "2026-07-06")
        path = save_copy("测试文案内容", d, "01_市场热点")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content, "测试文案内容")

    def test_save_snapshot(self):
        d = get_output_dir(str(self.output_dir), "2026-07-06")
        path = save_snapshot("市场数据快照", d)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "00_market_snapshot.md")

    def test_save_summary(self):
        d = get_output_dir(str(self.output_dir), "2026-07-06")
        results = [
            {"category": "市场热点", "success": True, "file": "01_市场热点.md"},
            {"category": "新闻动态", "success": False, "error": "API 错误"},
        ]
        path = save_summary(d, "2026-07-06", results)
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("市场热点", content)
        self.assertIn("API 错误", content)

    def test_output_dir_created(self):
        d = get_output_dir(str(self.output_dir), "2026-07-07")
        save_copy("内容", d, "01_市场热点")
        self.assertTrue(d.exists())


if __name__ == "__main__":
    unittest.main()
