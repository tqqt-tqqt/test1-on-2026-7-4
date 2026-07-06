"""A 股市场行情数据采集 —— 指数、板块、涨跌家数。"""

import logging
from typing import Optional

import pandas as pd

from .fetcher import DataFetcher, format_pct, format_volume

logger = logging.getLogger(__name__)


class MarketDataFetcher(DataFetcher):
    """获取 A 股市场综合行情数据。"""

    def __init__(self, indices: list = None, top_n: int = 5, delay: float = 2.0):
        super().__init__(delay=delay)
        self.indices = indices or ["000001", "399001", "399006"]
        self.top_n = top_n

    def fetch(self) -> dict:
        import akshare as ak

        result = {
            "indices": [],
            "top_sectors": [],
            "top_concepts": [],
            "top_gainers": [],
            "market_breadth": None,
            "fetched_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 1. 指数行情
        try:
            df_idx = ak.stock_zh_index_spot_em()
            for code in self.indices:
                row = df_idx[df_idx["代码"] == code]
                if not row.empty:
                    r = row.iloc[0]
                    result["indices"].append({
                        "name": r.get("名称", ""),
                        "code": r.get("代码", ""),
                        "price": round(float(r["最新价"]), 2),
                        "change_pct": float(r["涨跌幅"]),
                        "change_amount": float(r["涨跌额"]),
                        "volume_yi": float(r.get("成交额", 0)) / 1e8,
                    })
        except Exception as e:
            logger.warning("指数数据抓取失败: %s", e)

        # 2. 行业板块排行
        try:
            df_industry = ak.stock_board_industry_name_em()
            top = df_industry.head(self.top_n)
            for _, r in top.iterrows():
                result["top_sectors"].append({
                    "name": r.get("板块名称", ""),
                    "change_pct": float(r["涨跌幅"]),
                    "leading_stock": r.get("领涨股票", ""),
                })
        except Exception as e:
            logger.warning("行业板块数据抓取失败: %s", e)

        # 3. 概念板块排行
        try:
            df_concept = ak.stock_board_concept_name_em()
            top = df_concept.head(self.top_n)
            for _, r in top.iterrows():
                result["top_concepts"].append({
                    "name": r.get("板块名称", ""),
                    "change_pct": float(r["涨跌幅"]),
                    "leading_stock": r.get("领涨股票", ""),
                })
        except Exception as e:
            logger.warning("概念板块数据抓取失败: %s", e)

        # 4. 涨幅榜 + 涨跌家数
        try:
            df_spot = ak.stock_zh_a_spot_em()
            # 涨跌家数
            up = int((df_spot["涨跌幅"] > 0).sum())
            down = int((df_spot["涨跌幅"] < 0).sum())
            flat = int((df_spot["涨跌幅"] == 0).sum())
            result["market_breadth"] = {"up": up, "down": down, "flat": flat}
            # 涨幅榜
            top_up = df_spot.nlargest(self.top_n, "涨跌幅")
            for _, r in top_up.iterrows():
                result["top_gainers"].append({
                    "name": r.get("名称", ""),
                    "code": r.get("代码", ""),
                    "change_pct": float(r["涨跌幅"]),
                })
        except Exception as e:
            logger.warning("全市场数据抓取失败: %s", e)

        return result

    def is_trading_day(self) -> bool:
        """判断今日是否为交易日（数据非空且有指数行情）。"""
        data = self.safe_fetch()
        if data is None:
            return False
        return len(data.get("indices", [])) > 0


def format_market_snapshot(data: dict) -> str:
    """将市场数据格式化为 Markdown 快照。"""
    lines = ["# 今日市场数据快照", f"抓取时间：{data.get('fetched_at', '')}", ""]

    # 指数
    lines.append("## 主要指数")
    lines.append("| 指数 | 最新价 | 涨跌幅 | 涨跌额 | 成交额 |")
    lines.append("|------|--------|--------|--------|--------|")
    for idx in data.get("indices", []):
        lines.append(
            f"| {idx['name']} | {idx['price']} | {format_pct(idx['change_pct'])} "
            f"| {idx.get('change_amount', '')} | {format_volume(idx.get('volume_yi', 0))} |"
        )
    lines.append("")

    # 涨跌家数
    breadth = data.get("market_breadth")
    if breadth:
        lines.append("## 涨跌家数")
        lines.append(f"上涨 {breadth['up']} 家 / 下跌 {breadth['down']} 家 / 平盘 {breadth['flat']} 家")
        lines.append("")

    # 行业板块
    lines.append("## 涨幅领先行业板块")
    for s in data.get("top_sectors", []):
        lines.append(f"- {s['name']}：{format_pct(s['change_pct'])}（领涨：{s.get('leading_stock', '')}）")
    lines.append("")

    # 概念板块
    lines.append("## 涨幅领先概念板块")
    for c in data.get("top_concepts", []):
        lines.append(f"- {c['name']}：{format_pct(c['change_pct'])}（领涨：{c.get('leading_stock', '')}）")
    lines.append("")

    # 涨幅榜
    lines.append("## 涨幅榜个股")
    for g in data.get("top_gainers", []):
        lines.append(f"- {g['name']}（{g['code']}）：{format_pct(g['change_pct'])}")

    return "\n".join(lines)
