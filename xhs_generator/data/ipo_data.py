"""IPO 新股数据 —— 从证监会 / 交易所公开信息抓取。"""

import re
import logging
from datetime import datetime
from typing import Optional

from .fetcher import DataFetcher, http_get, normalize_title

logger = logging.getLogger(__name__)

# ── 数据源 ─────────────────────────────────────────────────────

# 证券时报 IPO 频道
STCN_IPO_URL = "https://data.stcn.com/ipo/"
STCN_REFERER = "https://www.stcn.com/"

# 深圳证券交易所 - 新股申购
SZSE_IPO_URL = "https://www.szse.cn/api/disc/announcement/newStockList"


class IPODataFetcher(DataFetcher):
    """获取近期 IPO / 新股信息。"""

    def __init__(self, top_n: int = 5, delay: float = 1.0):
        super().__init__(delay=delay)
        self.top_n = top_n

    def fetch(self) -> dict:
        result = {
            "new_stocks": [],
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 1. 尝试证券时报 IPO 频道
        stocks = self._fetch_stcn_ipo()
        if stocks:
            result["new_stocks"] = stocks[:self.top_n]
            return result

        # 2. 尝试深交所新股接口
        stocks = self._fetch_szse_ipo()
        if stocks:
            result["new_stocks"] = stocks[:self.top_n]
            return result

        return result

    def _fetch_stcn_ipo(self) -> list[dict]:
        """从证券时报 IPO 频道抓取。"""
        stocks = []
        try:
            html = http_get(STCN_IPO_URL, referer=STCN_REFERER,
                            encoding="utf-8", timeout=15, retries=2)
            if not html:
                return stocks

            # 匹配新股表格行
            # 典型结构：<td>股票简称</td> <td>股票代码</td> <td>发行价格</td> <td>发行日期</td>
            row_pattern = re.compile(
                r'<tr[^>]*>.*?'
                r'<td[^>]*>\s*([一-龥\w]{2,8})\s*</td>\s*'
                r'<td[^>]*>\s*(\d{6})\s*</td>.*?'
                r'<td[^>]*>\s*([\d.]+)\s*</td>.*?'
                r'<td[^>]*>\s*(\d{4}-\d{2}-\d{2})\s*</td>',
                re.DOTALL
            )
            for m in row_pattern.finditer(html):
                stocks.append({
                    "name": m.group(1).strip(),
                    "code": m.group(2).strip(),
                    "ipo_price": m.group(3).strip(),
                    "ipo_date": m.group(4).strip(),
                })

            # 如果表格模式没匹配到，尝试提取含"新股"关键词的链接
            if not stocks:
                for m in re.finditer(
                    r'<a[^>]*href="([^"]*)"[^>]*>'
                    r'(.{0,30}(?:申购|新股|IPO|上市).{0,30})</a>',
                    html
                ):
                    title = normalize_title(re.sub(r'<[^>]+>', '', m.group(2)))
                    if len(title) >= 4:
                        stocks.append({
                            "name": title,
                            "code": "",
                            "ipo_price": "",
                            "ipo_date": "",
                        })

        except Exception as e:
            logger.warning("证券时报 IPO 抓取失败: %s", e)

        return stocks

    def _fetch_szse_ipo(self) -> list[dict]:
        """从深交所新股接口抓取。"""
        stocks = []
        try:
            from .fetcher import http_get_json
            data = http_get_json(
                SZSE_IPO_URL,
                referer="https://www.szse.cn/",
                timeout=10,
                retries=1,
            )
            if data:
                records = data.get("data", data.get("records", []))
                for r in records[:self.top_n]:
                    stocks.append({
                        "name": str(r.get("secName", r.get("stockName", ""))),
                        "code": str(r.get("secCode", r.get("stockCode", ""))),
                        "ipo_price": str(r.get("issuePrice", r.get("price", ""))),
                        "ipo_date": str(r.get("issueDate", r.get("date", ""))),
                    })
        except Exception:
            pass  # 深交所接口可能不可用，静默失败

        return stocks


# ── 快照格式化 ──────────────────────────────────────────────────

def format_ipo_snapshot(data: dict) -> str:
    """将 IPO 数据格式化为 Markdown。"""
    if data is None:
        data = {}
    lines = ["## 近期新股 / IPO",
             f"抓取时间：{data.get('fetched_at', '')}",
             f"数据来源：证券时报 / 深交所",
             ""]

    stocks = data.get("new_stocks", [])
    if not stocks:
        lines.append("近期暂无新股申购信息，或数据暂不可用。")
        lines.append("")
        return "\n".join(lines)

    lines.append("| 股票简称 | 股票代码 | 发行价格 | 发行日期 |")
    lines.append("|----------|----------|----------|----------|")
    for s in stocks:
        lines.append(
            f"| {s['name']} | {s['code'] or 'N/A'} | "
            f"{s['ipo_price'] or 'N/A'} | {s['ipo_date'] or '待定'} |"
        )
    lines.append("")
    return "\n".join(lines)
