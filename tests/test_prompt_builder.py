"""提示词构建器测试 —— JSON 结构输出版。"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xhs_generator.generator.prompt_builder import (
    get_prompt,
    build_base_context,
    BROKERAGE_SIGNATURE,
    CATEGORY_NAMES,
    PROMPT_BUILDERS,
    _json_output_spec,
)


SAMPLE_CONFIG = {
    "theme": "券商营业部日常运营",
    "tone": "专业、平实、亲切",
    "hashtags": ["券商", "A股", "投资教育"],
    "length": "700字左右",
    "audience": "有投资需求的年轻用户",
    "brokerage": {
        "name": "广发证券 成都麓山大道营业部",
        "slogan": "您的身边理财管家",
        "contact": "预约1对1专业投顾",
    },
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
    "all_news": [
        {"title": "重磅政策出台", "source": "新华财经", "time": "09:00", "summary": ""},
        {"title": "A股开盘走高", "source": "财联社", "time": "09:30", "summary": ""},
    ],
    "eastmoney_news": [],
    "cls_news": [],
}

SAMPLE_IPO = {
    "new_stocks": [{"name": "测试科技", "code": "688001", "ipo_price": "29.80", "ipo_date": "2026-07-10"}],
}


class TestJsonOutputSpec(unittest.TestCase):
    def test_spec_contains_json_fields(self):
        spec = _json_output_spec(SAMPLE_CONFIG)
        self.assertIn("title", spec)
        self.assertIn("body", spec)
        self.assertIn("image_texts", spec)
        self.assertIn("tags", spec)

    def test_spec_contains_brokerage_signature(self):
        spec = _json_output_spec(SAMPLE_CONFIG)
        self.assertIn("广发证券", spec)
        self.assertIn("成都麓山大道营业部", spec)

    def test_spec_contains_compliance(self):
        spec = _json_output_spec(SAMPLE_CONFIG)
        self.assertIn("风险提示", spec)

    def test_brokerage_signature_constant(self):
        self.assertIn("广发证券", BROKERAGE_SIGNATURE)
        self.assertIn("麓山大道", BROKERAGE_SIGNATURE)
        self.assertIn("1对1专业投顾", BROKERAGE_SIGNATURE)


class TestPromptBuilders(unittest.TestCase):
    """每个分类提示词生成并验证关键内容。"""

    def test_all_categories_have_builder(self):
        for cat in CATEGORY_NAMES:
            self.assertIn(cat, PROMPT_BUILDERS, f"{cat} 缺少提示词构建函数")

    def _check_prompt(self, category: str):
        prompt = get_prompt(category, SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-08")
        # 关键元素检查
        self.assertIn("JSON", prompt, f"{category} 提示词应包含 JSON 输出要求")
        self.assertIn("title", prompt)
        self.assertIn("image_texts", prompt)
        self.assertIn("tags", prompt)
        self.assertIn(BROKERAGE_SIGNATURE[:10], prompt)  # 营业部署名
        self.assertIn("风险提示", prompt)
        # 数据注入检查
        self.assertIn("上证指数", prompt)
        self.assertIn("3456.78", prompt)
        self.assertIn("广发证券", prompt)

    def test_market_hotspot(self):
        self._check_prompt("市场热点")

    def test_news(self):
        self._check_prompt("新闻动态")

    def test_ipo(self):
        self._check_prompt("IPO")

    def test_advisory(self):
        self._check_prompt("投顾服务")

    def test_education(self):
        self._check_prompt("投资者教育")

    def test_daily_digest(self):
        self._check_prompt("每日精选")

    def test_unknown_category_raises(self):
        with self.assertRaises(ValueError):
            get_prompt("不存在的分类", SAMPLE_MARKET, SAMPLE_NEWS, SAMPLE_IPO, SAMPLE_CONFIG, "2026-07-08")

    def test_build_base_context_handles_none(self):
        ctx = build_base_context(None, None, None, SAMPLE_CONFIG, "2026-07-08")
        self.assertIn("2026-07-08", ctx)
        self.assertIn("暂不可用", ctx)


class TestTitleLength(unittest.TestCase):
    """验证提示词中要求标题 ≤20 字。"""

    def test_title_limit_in_spec(self):
        spec = _json_output_spec(SAMPLE_CONFIG)
        self.assertIn("≤20", spec)


if __name__ == "__main__":
    unittest.main()
