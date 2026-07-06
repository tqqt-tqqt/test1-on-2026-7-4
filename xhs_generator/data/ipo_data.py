"""IPO 新股数据采集。"""

import logging
from typing import Optional

from .fetcher import DataFetcher

logger = logging.getLogger(__name__)


class IPODataFetcher(DataFetcher):
    """获取待上市新股 / IPO 日历数据。"""

    def __init__(self, top_n: int = 5, delay: float = 2.0):
        super().__init__(delay=delay)
        self.top_n = top_n

    def fetch(self) -> dict:
        import akshare as ak

        result = {
            "new_stocks": [],
            "fetched_at": "",
        }

        # 待上市新股
        try:
            df_new = ak.stock_zh_a_new()
            for _, r in df_new.head(self.top_n).iterrows():
                result["new_stocks"].append({
                    "name": str(r.get("股票简称", r.get("name", ""))),
                    "code": str(r.get("股票代码", r.get("code", ""))),
                    "ipo_price": str(r.get("发行价格", r.get("price", ""))),
                    "ipo_date": str(r.get("上网发行日期", r.get("date", ""))),
                })
        except Exception as e:
            logger.warning("IPO 新股数据抓取失败: %s", e)

        from datetime import datetime
        result["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return result


def format_ipo_snapshot(data: dict) -> str:
    """将 IPO 数据格式化为 Markdown。"""
    lines = ["## 近期新股 / IPO", f"抓取时间：{data.get('fetched_at', '')}", ""]

    stocks = data.get("new_stocks", [])
    if not stocks:
        lines.append("近期无待上市新股信息。")
    else:
        lines.append("| 股票简称 | 股票代码 | 发行价格 | 上网发行日期 |")
        lines.append("|----------|----------|----------|-------------|")
        for s in stocks:
            lines.append(
                f"| {s['name']} | {s['code']} | {s['ipo_price']} | {s['ipo_date']} |"
            )
    lines.append("")
    return "\n".join(lines)
