import unittest
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location("generate_xhs_copy", Path(__file__).resolve().parents[1] / "generate_xhs_copy.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class GenerateXhsCopyTests(unittest.TestCase):
    def test_select_content_type_returns_known_category(self):
        config = {
            "content_categories": ["市场热点", "新闻动态", "IPO", "投顾服务", "投资者教育"],
            "theme": "券商营业部日常运营",
        }
        selected = module.select_content_type(config, "2026-07-05")
        self.assertIn(selected, config["content_categories"])

    def test_build_prompt_mentions_risk_warning_and_broker_context(self):
        config = {
            "theme": "券商营业部日常运营",
            "tone": "专业、平实、亲切",
            "audience": "有投资需求的年轻用户",
            "hashtags": ["券商", "A股", "投资教育"],
            "content_categories": ["市场热点"],
        }
        prompt = module.build_prompt(config, "2026-07-05")
        self.assertIn("券商营业部", prompt)
        self.assertIn("风险提示", prompt)


if __name__ == "__main__":
    unittest.main()
