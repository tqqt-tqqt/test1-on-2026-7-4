"""数据层测试。"""

import unittest
from pathlib import Path
import sys

# 确保项目根目录在 sys.path 中
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xhs_generator.data.fetcher import format_pct, format_volume, DataFetcher
from xhs_generator.data.market_data import MarketDataFetcher, format_market_snapshot
from xhs_generator.data.news_data import NewsDataFetcher, format_news_snapshot
from xhs_generator.data.ipo_data import IPODataFetcher, format_ipo_snapshot


class TestFormatUtils(unittest.TestCase):
    def test_format_pct_positive(self):
        self.assertEqual(format_pct(3.56), "+3.56%")

    def test_format_pct_negative(self):
        self.assertEqual(format_pct(-1.23), "-1.23%")

    def test_format_pct_none(self):
        self.assertEqual(format_pct(None), "N/A")

    def test_format_volume(self):
        self.assertEqual(format_volume(123.45), "123.45亿")

    def test_format_volume_none(self):
        self.assertEqual(format_volume(None), "N/A")


class TestMarketDataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = MarketDataFetcher(delay=0)

    def test_fetch_returns_dict_with_keys(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("indices", data)
        self.assertIn("top_sectors", data)
        self.assertIn("top_concepts", data)
        self.assertIn("top_gainers", data)
        self.assertIn("market_breadth", data)
        self.assertIn("fetched_at", data)

    def test_fetch_indices_have_expected_fields(self):
        data = self.fetcher.safe_fetch()
        if data and data["indices"]:
            idx = data["indices"][0]
            self.assertIn("name", idx)
            self.assertIn("price", idx)
            self.assertIn("change_pct", idx)

    def test_format_market_snapshot(self):
        sample = {
            "indices": [
                {"name": "上证指数", "code": "000001", "price": 3456.78, "change_pct": 0.35, "change_amount": 12.0, "volume_yi": 4521.30}
            ],
            "top_sectors": [{"name": "半导体", "change_pct": 3.5, "leading_stock": "中芯国际"}],
            "top_concepts": [{"name": "ChatGPT", "change_pct": 5.2, "leading_stock": "科大讯飞"}],
            "top_gainers": [{"name": "测试股", "code": "000001", "change_pct": 10.0}],
            "market_breadth": {"up": 2100, "down": 1800, "flat": 300},
            "fetched_at": "2026-07-06 15:00:00",
        }
        snapshot = format_market_snapshot(sample)
        self.assertIn("上证指数", snapshot)
        self.assertIn("半导体", snapshot)
        self.assertIn("2100", snapshot)


class TestNewsDataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = NewsDataFetcher(delay=0)

    def test_fetch_returns_dict(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("eastmoney_news", data)
        self.assertIn("cls_news", data)

    def test_get_news_summary(self):
        data = {
            "eastmoney_news": [{"title": "新闻1", "summary": "", "time": "10:00"}],
            "cls_news": [{"title": "新闻2", "content": "", "time": "10:30"}],
        }
        items = self.fetcher.get_news_summary(data)
        self.assertEqual(len(items), 2)


class TestIPODataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = IPODataFetcher(delay=0)

    def test_fetch_returns_dict(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("new_stocks", data)


if __name__ == "__main__":
    unittest.main()
