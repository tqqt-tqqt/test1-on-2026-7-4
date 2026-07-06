"""财经新闻数据采集。"""

import logging
from typing import Optional

from .fetcher import DataFetcher

logger = logging.getLogger(__name__)


class NewsDataFetcher(DataFetcher):
    """获取财经快讯（东方财富 + 财联社）。"""

    def __init__(self, top_n: int = 5, delay: float = 2.0):
        super().__init__(delay=delay)
        self.top_n = top_n

    def fetch(self) -> dict:
        import akshare as ak

        result = {
            "eastmoney_news": [],
            "cls_news": [],
            "fetched_at": "",
        }

        # 东方财富全球快讯
        try:
            df_em = ak.stock_info_global_em()
            for _, r in df_em.head(self.top_n).iterrows():
                result["eastmoney_news"].append({
                    "title": str(r.get("title", "")),
                    "summary": str(r.get("summary", ""))[:200] if r.get("summary") else "",
                    "time": str(r.get("publish_time", "")),
                })
        except Exception as e:
            logger.warning("东方财富快讯抓取失败: %s", e)

        # 财联社电报
        try:
            df_cls = ak.stock_info_global_cls()
            for _, r in df_cls.head(self.top_n).iterrows():
                result["cls_news"].append({
                    "title": str(r.get("title", "")),
                    "content": str(r.get("content", ""))[:200] if r.get("content") else "",
                    "time": str(r.get("ctime", "")),
                })
        except Exception as e:
            logger.warning("财联社电报抓取失败: %s", e)

        from datetime import datetime
        result["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return result

    def get_news_summary(self, data: Optional[dict] = None) -> list:
        """获取新闻摘要列表，合并两个来源。"""
        if data is None:
            data = self.safe_fetch() or {}
        items = []
        for n in data.get("eastmoney_news", []):
            items.append(f"[东方财富] {n['title']}")
        for n in data.get("cls_news", []):
            items.append(f"[财联社] {n['title']}")
        return items


def format_news_snapshot(data: dict) -> str:
    """将新闻数据格式化为 Markdown。"""
    lines = ["## 今日财经快讯", f"抓取时间：{data.get('fetched_at', '')}", ""]

    lines.append("### 东方财富快讯")
    for n in data.get("eastmoney_news", []):
        lines.append(f"- **{n['title']}** ({n['time']})")
        if n.get("summary"):
            lines.append(f"  {n['summary']}")
    lines.append("")

    lines.append("### 财联社电报")
    for n in data.get("cls_news", []):
        lines.append(f"- **{n['title']}** ({n['time']})")
        if n.get("content"):
            lines.append(f"  {n['content']}")
    lines.append("")

    return "\n".join(lines)
