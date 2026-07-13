"""A 股市场行情数据 —— 新浪财经 API。"""

import re
import logging
from datetime import datetime
from typing import Optional

from .fetcher import DataFetcher, http_get, format_pct, format_volume

logger = logging.getLogger(__name__)

# ── 新浪行情接口 ────────────────────────────────────────────────

SINA_INDEX_URL = "https://hq.sinajs.cn/list="
SINA_REFERER = "https://finance.sina.com.cn"

# 指数代码映射
INDEX_CODES = {
    "000001": "sh000001",   # 上证指数
    "399001": "sz399001",   # 深证成指
    "399006": "sz399006",   # 创业板指
    "000688": "sh000688",   # 科创50
    "000300": "sh000300",   # 沪深300
}

# 板块排行（新浪行业板块）
SINA_BOARD_URL = "https://vip.stock.finance.sina.com.cn/q/go.php/vIndustryRank/kind/rank/"
# 新浪全市场涨跌统计
SINA_MARKET_URL = "https://hq.sinajs.cn/list="


def _parse_sina_line(line: str) -> Optional[dict]:
    """解析新浪单条行情数据。

    格式：var hq_str_sh000001="名称,今开,昨收,最新,最高,最低,...,日期,时间";
    字段索引（上证指数为例）：
    0:名称 1:今开 2:昨收 3:最新 4:最高 5:最低
    8:涨跌额(可能为空) 9:成交量(手) 10:成交额(万) ...
    30:日期 31:时间
    """
    m = re.search(r'hq_str_\w+="(.*)"', line)
    if not m:
        return None
    fields = m.group(1).split(",")
    if len(fields) < 6:
        return None
    try:
        name = fields[0]
        price = float(fields[3]) if fields[3] else 0
        prev_close = float(fields[2]) if fields[2] else 0
        change_pct = ((price - prev_close) / prev_close * 100) if prev_close != 0 else 0
        volume = float(fields[9]) / 1e8 if len(fields) > 9 and fields[9] else 0  # 手→亿
        return {
            "name": name,
            "code": "",
            "price": round(price, 2),
            "change_pct": round(change_pct, 2),
            "change_amount": round(price - prev_close, 2),
            "volume_yi": round(volume, 2),
        }
    except (ValueError, IndexError):
        return None


class MarketDataFetcher(DataFetcher):
    """通过新浪财经 API 获取 A 股市场行情。"""

    def __init__(self, indices: list = None, top_n: int = 5, delay: float = 1.0):
        super().__init__(delay=delay)
        self.index_codes = indices or ["000001", "399001", "399006"]
        self.top_n = top_n

    def fetch(self) -> dict:
        result = {
            "indices": [],
            "top_sectors": [],
            "top_concepts": [],
            "top_gainers": [],
            "market_breadth": None,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 1. 指数行情
        codes = [INDEX_CODES.get(c, f"sh{c}" if c.startswith("0") else f"sz{c}")
                 for c in self.index_codes]
        url = SINA_INDEX_URL + ",".join(codes)
        text = http_get(url, referer=SINA_REFERER, encoding="gbk")
        if text:
            for line in text.strip().split("\n"):
                parsed = _parse_sina_line(line)
                if parsed:
                    # 回填代码
                    for orig_code, sina_code in INDEX_CODES.items():
                        if sina_code in line:
                            parsed["code"] = orig_code
                            break
                    result["indices"].append(parsed)
        else:
            logger.warning("新浪指数行情获取失败")

        # 2. 行业板块排行（尝试新浪行业板块页面）
        self._fetch_sectors(result)

        # 3. 涨跌家数（尝试新浪大盘概况）
        self._fetch_market_breadth(result)

        return result

    def _fetch_sectors(self, result: dict):
        """抓取行业板块排行。"""
        try:
            # 新浪行业板块排名页面
            text = http_get(
                f"{SINA_BOARD_URL}",
                referer=SINA_REFERER,
                params={"p": "1", "num": str(self.top_n), "sort": "changepercent", "asc": "0"},
                encoding="gbk",
                timeout=10,
                retries=1,
            )
            if not text:
                return
            # 简易 HTML 解析：匹配板块名和涨跌幅
            # 新浪页面结构：<td><a>板块名</a></td><td>涨跌幅</td>
            pattern = re.compile(
                r'<td[^>]*>\s*<a[^>]*>([^<]+)</a>\s*</td>\s*'
                r'<td[^>]*>([\d.-]+)</td>',
                re.DOTALL
            )
            matches = pattern.findall(text)
            for name, pct in matches[:self.top_n]:
                try:
                    result["top_sectors"].append({
                        "name": name.strip(),
                        "change_pct": float(pct),
                        "leading_stock": "",
                    })
                except ValueError:
                    continue
        except Exception as e:
            logger.warning("板块数据抓取失败: %s", e)

    def _fetch_market_breadth(self, result: dict):
        """尝试获取涨跌家数。"""
        try:
            # 新浪大盘概况页面
            text = http_get(
                "https://vip.stock.finance.sina.com.cn/mkt/",
                referer=SINA_REFERER,
                encoding="gbk",
                timeout=10,
                retries=1,
            )
            if not text:
                return
            # 匹配涨跌家数（格式：上涨xxx家 下跌xxx家）
            up_m = re.search(r'上涨[：:\s]*(\d+)', text)
            down_m = re.search(r'下跌[：:\s]*(\d+)', text)
            if up_m and down_m:
                result["market_breadth"] = {
                    "up": int(up_m.group(1)),
                    "down": int(down_m.group(1)),
                    "flat": 0,
                }
        except Exception as e:
            logger.warning("涨跌家数抓取失败: %s", e)

    def is_trading_day(self) -> bool:
        """判断今日是否交易日。指数有涨跌变化即为交易日。"""
        data = self.safe_fetch()
        if data is None:
            return False
        indices = data.get("indices", [])
        if not indices:
            return False
        # 所有指数涨跌幅均为 0 → 非交易日
        all_zero = all(abs(idx.get("change_pct", 0)) < 0.01 for idx in indices)
        return not all_zero


# ── 快照格式化 ──────────────────────────────────────────────────

def format_market_snapshot(data: dict) -> str:
    """将市场数据格式化为 Markdown 快照。"""
    if data is None:
        data = {}
    lines = ["# 今日市场数据快照",
             f"抓取时间：{data.get('fetched_at', '')}",
             f"数据来源：新浪财经",
             ""]

    lines.append("## 主要指数")
    indices = data.get("indices", [])
    if indices:
        lines.append("| 指数 | 最新价 | 涨跌幅 | 涨跌额 | 成交额 |")
        lines.append("|------|--------|--------|--------|--------|")
        for idx in indices:
            lines.append(
                f"| {idx['name']} | {idx['price']} | {format_pct(idx['change_pct'])} "
                f"| {idx.get('change_amount', '')} | {format_volume(idx.get('volume_yi', 0))} |"
            )
    else:
        lines.append("（今日指数数据暂不可用）")
    lines.append("")

    breadth = data.get("market_breadth")
    if breadth:
        lines.append("## 涨跌家数")
        lines.append(f"上涨 {breadth['up']} 家 / 下跌 {breadth['down']} 家 / 平盘 {breadth.get('flat', 0)} 家")
        lines.append("")

    sectors = data.get("top_sectors", [])
    if sectors:
        lines.append("## 涨幅领先行业板块")
        for s in sectors:
            lines.append(f"- {s['name']}：{format_pct(s['change_pct'])}")
        lines.append("")

    concepts = data.get("top_concepts", [])
    if concepts:
        lines.append("## 热门概念板块")
        for c in concepts:
            lines.append(f"- {c['name']}：{format_pct(c['change_pct'])}")
        lines.append("")

    gainers = data.get("top_gainers", [])
    if gainers:
        lines.append("## 涨幅榜个股")
        for g in gainers:
            lines.append(f"- {g['name']}（{g['code']}）：{format_pct(g['change_pct'])}")

    return "\n".join(lines)
