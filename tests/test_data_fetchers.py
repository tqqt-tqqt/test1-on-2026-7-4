"""数据层测试。"""

import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from xhs_generator.data.fetcher import (
    format_pct,
    format_volume,
    normalize_title,
    build_cls_params,
    DataFetcher,
)
from xhs_generator.data.market_data import MarketDataFetcher, format_market_snapshot, _parse_sina_line
from xhs_generator.data.news_data import (
    ClsTelegraphSource,
    StcnNewsSource,
    CnfinNewsSource,
    JiemianNewsSource,
    NewsDataFetcher,
    format_news_snapshot,
)
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

    def test_normalize_title(self):
        self.assertEqual(normalize_title("  你好   世界  "), "你好 世界")

    def test_build_cls_params(self):
        params = build_cls_params(last_time="", rn=20)
        self.assertIn("sign", params)
        self.assertEqual(params["app"], "CailianpressWeb")
        self.assertEqual(params["rn"], "20")


class TestSinaLineParsing(unittest.TestCase):
    def test_parse_index_line(self):
        line = 'var hq_str_sh000001="上证指数,3100.00,3090.00,3110.50,3120.00,3080.00,0,0,0,5000000,500000,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,2026-07-06,15:00:00";'
        result = _parse_sina_line(line)
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "上证指数")
        self.assertEqual(result["price"], 3110.50)

    def test_parse_invalid_line(self):
        self.assertIsNone(_parse_sina_line("invalid"))
        self.assertIsNone(_parse_sina_line('var hq_str_x="";'))


class TestMarketDataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = MarketDataFetcher(delay=0.1)

    def test_fetch_returns_dict_with_keys(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("indices", data)
        self.assertIn("top_sectors", data)
        self.assertIn("fetched_at", data)

    def test_format_market_snapshot(self):
        sample = {
            "indices": [
                {"name": "上证指数", "code": "000001", "price": 3456.78,
                 "change_pct": 0.35, "change_amount": 12.0, "volume_yi": 4521.30}
            ],
            "top_sectors": [{"name": "半导体", "change_pct": 3.5, "leading_stock": ""}],
            "market_breadth": {"up": 2100, "down": 1800, "flat": 0},
            "fetched_at": "2026-07-06 15:00:00",
        }
        snapshot = format_market_snapshot(sample)
        self.assertIn("上证指数", snapshot)
        self.assertIn("新浪财经", snapshot)
        self.assertIn("半导体", snapshot)

    def test_format_market_snapshot_none(self):
        snapshot = format_market_snapshot(None)
        self.assertIn("暂不可用", snapshot)


class TestNewsDataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = NewsDataFetcher(top_n=5, delay=0.1)

    def test_fetch_returns_dict(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("all_news", data)
        self.assertIn("eastmoney_news", data)
        self.assertIn("cls_news", data)
        self.assertIn("source_stats", data)

    def test_get_news_summary(self):
        data = {
            "all_news": [
                {"title": "新闻1", "source": "财联社", "time": "10:00"},
                {"title": "新闻2", "source": "证券时报", "time": "10:30"},
            ],
            "eastmoney_news": [],
            "cls_news": [],
            "source_stats": {},
        }
        items = self.fetcher.get_news_summary(data)
        self.assertGreaterEqual(len(items), 1)

    def test_format_news_snapshot(self):
        data = {
            "all_news": [
                {"title": "测试新闻", "source": "财联社", "time": "10:00", "summary": ""}
            ],
            "source_stats": {"ClsTelegraphSource": 1},
            "fetched_at": "2026-07-06 15:00:00",
        }
        text = format_news_snapshot(data)
        self.assertIn("财联社", text)
        self.assertIn("测试新闻", text)


class TestIndividualSources(unittest.TestCase):
    """单独测试每个新闻源（可能因网络问题失败）。"""

    def test_cls_telegraph(self):
        src = ClsTelegraphSource(top_n=5)
        items = src.fetch()
        self.assertIsInstance(items, list)
        if items:
            self.assertIn("title", items[0])
            self.assertEqual(items[0]["source"], "财联社")

    def test_stcn_news(self):
        src = StcnNewsSource(top_n=5)
        items = src.fetch()
        self.assertIsInstance(items, list)

    def test_cnfin_news(self):
        src = CnfinNewsSource(top_n=5)
        items = src.fetch()
        self.assertIsInstance(items, list)

    def test_jiemian_news(self):
        src = JiemianNewsSource(top_n=5)
        items = src.fetch()
        self.assertIsInstance(items, list)


class TestIPODataFetcher(unittest.TestCase):
    def setUp(self):
        self.fetcher = IPODataFetcher(delay=0.1)

    def test_fetch_returns_dict(self):
        data = self.fetcher.safe_fetch()
        self.assertIsNotNone(data)
        self.assertIn("new_stocks", data)

    def test_format_ipo_snapshot(self):
        data = {
            "new_stocks": [
                {"name": "测试科技", "code": "688001", "ipo_price": "29.80", "ipo_date": "2026-07-10"}
            ],
            "fetched_at": "2026-07-06",
        }
        text = format_ipo_snapshot(data)
        self.assertIn("测试科技", text)
        self.assertIn("688001", text)


if __name__ == "__main__":
    unittest.main()
