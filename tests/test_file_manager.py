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
    save_post,
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
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        self.assertEqual(d, self.output_dir / "2026-07-08")

    def test_save_and_read_copy(self):
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        path = save_copy("测试文案内容", d, "01_市场热点")
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertEqual(content, "测试文案内容")

    def test_save_post_structured(self):
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        path = save_post(
            d, "01_市场热点",
            title="今日A股复盘：半导体领涨",
            body="正文内容约700字，包含详细分析...\n\n🏦 广发证券 成都麓山大道营业部 | 您的身边理财管家\n📞 预约1对1专业投顾",
            image_texts=["第1页：核心观点总结", "第2页：数据解读", "第3页：投资建议"],
            tags=["#A股", "#半导体", "#投资", "#理财", "#今日看盘",
                  "#财经", "#券商", "#投教", "#市场热点", "#股票",
                  "#小白理财", "#每日复盘", "#金融", "#复盘", "#干货"],
        )
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        # 检查各要素
        self.assertIn("今日A股复盘：半导体领涨", content)
        self.assertIn("## 正文", content)
        self.assertIn("广发证券", content)
        self.assertIn("## 图片文字", content)
        self.assertIn("### 第1页", content)
        self.assertIn("### 第3页", content)
        self.assertIn("## 标签", content)
        self.assertIn("#A股", content)

    def test_save_post_minimal(self):
        """最少内容——无图片文字。"""
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        path = save_post(
            d, "02_新闻动态",
            title="短标题",
            body="正文。",
            image_texts=[],
            tags=["#测试"],
        )
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("短标题", content)

    def test_save_snapshot(self):
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        path = save_snapshot("市场数据快照", d)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "00_market_snapshot.md")

    def test_save_summary(self):
        d = get_output_dir(str(self.output_dir), "2026-07-08")
        results = [
            {"category": "市场热点", "success": True, "file": "01_市场热点.md"},
            {"category": "新闻动态", "success": False, "error": "API 错误"},
        ]
        path = save_summary(d, "2026-07-08", results)
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        self.assertIn("市场热点", content)
        self.assertIn("API 错误", content)

    def test_output_dir_created(self):
        d = get_output_dir(str(self.output_dir), "2026-07-09")
        save_copy("内容", d, "01_市场热点")
        self.assertTrue(d.exists())


if __name__ == "__main__":
    unittest.main()
