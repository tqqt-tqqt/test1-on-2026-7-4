"""提示词构建器测试。"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xhs_generator.generator.prompt_builder import (
    get_prompt,
    build_base_context,
    build_common_requirements,
    CATEGORY_NAMES,
    PROMPT_BUILDERS,
)


SAMPLE_CONFIG = {
    "theme": "券商营业部日常运营",
    "tone": "专业、平实、亲切",
    "hashtags": ["券商", "A股", "投资教育"],
    "length": "150-220字",
    "audience": "有投资需求的年轻用户",
}

SAMPLE_MARKET = {
    "indices": [
        {"name": "上证指数", "code": "000001", "price": 3456.78, "change_pct": 0.35, "change_amount": 12.0, "volume_yi": 4521.30},
        {"name": "深证成指", "code": "399001", "price": 11234.56, "change_pct": -0.12, "change_amount": -13.5, "volume_yi": 6789.10},
    ],
    "top_sectors": [{"name": "半导体", "change_pct": 3.5, "leading_stock": "中芯国际"}],
    "top_concepts": [{"name": "ChatGPT", "change_pct": 5.2, "leading_stock": "科大讯飞"}],
    "top_gainers": [{"name": "测试股", "code": "000001", "change_pct": 10.0}],
    "market_breadth": {"up": 2100, "down": 1800, "flat": 300},
}

SAMPLE_NEWS = {
    "eastmoney_news": [{"title": "重磅政策出台", "summary": "国务院发布...", "time": "09:00"}],
    "cls_news": [{"title": "A股开盘走高", "content": "三大指数集体高开...", "time": "09:30"}],
}

SAMPLE_IPO = {
    "new_stocks": [{"name": "测试科技", "code": "688001", "ipo_price": "29.80", "ipo_date": "2026-07-10"}],
}


class TestPromptBuilders(unittest.TestCase):
    def test_all_categories_have_builder(self):
        for cat in CATEGORY_NAMES:
            self.assertIn(cat, PROMPT_BUILDERS, f"{cat} 缺少提示词构建函数")

    def test_get_prompt_market_hotspot(self):
        prompt = get_prompt("市场热点", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("上证指数", prompt)
        self.assertIn("3456.78", prompt)
        self.assertIn("风险提示", prompt)
        self.assertIn("券商", prompt)

    def test_get_prompt_news(self):
        prompt = get_prompt("新闻动态", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("重磅政策出台", prompt)
        self.assertIn("风险提示", prompt)

    def test_get_prompt_ipo(self):
        prompt = get_prompt("IPO", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("测试科技", prompt)
        self.assertIn("风险提示", prompt)

    def test_get_prompt_advisory(self):
        prompt = get_prompt("投顾服务", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("投顾", prompt)
        self.assertIn("风险提示", prompt)

    def test_get_prompt_education(self):
        prompt = get_prompt("投资者教育", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("投资", prompt)
        self.assertIn("风险提示", prompt)

    def test_get_prompt_daily_digest(self):
        prompt = get_prompt("每日精选", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("上证指数", prompt)
        self.assertIn("风险提示", prompt)

    def test_get_prompt_unknown_category(self):
        with self.assertRaises(ValueError):
            get_prompt("不存在的分类", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-06")

    def test_build_base_context_handles_none_data(self):
        ctx = build_base_context(None, None, None, SAMPLE_CONFIG, "2026-07-06")
        self.assertIn("2026-07-06", ctx)
        self.assertIn("暂不可用", ctx)

    def test_build_common_requirements(self):
        req = build_common_requirements(SAMPLE_CONFIG)
        self.assertIn("风险提示", req)
        self.assertIn("券商", req)
        self.assertIn("A股", req)


class TestLegacyCompatibility(unittest.TestCase):
    """确保与旧 generate_xhs_copy.py 接口的兼容性。"""

    def test_select_content_type_remains_compatible(self):
        """旧版 select_content_type 逻辑已内化到 CATEGORY_NAMES 遍历中。"""
        # 验证所有旧分类都存在于新系统中
        legacy_cats = ["市场热点", "新闻动态", "IPO", "投顾服务", "投资者教育"]
        for cat in legacy_cats:
            self.assertIn(cat, CATEGORY_NAMES)
        self.assertIn("每日精选", CATEGORY_NAMES)  # 新增


if __name__ == "__main__":
    unittest.main()
