"""财经新闻数据采集 —— 财联社 / 证券时报 / 新华财经 / 界面新闻。

每个来源独立抓取，任一失败不影响其他源。最终合并去重排序。
"""

import re
import logging
import time
from datetime import datetime
from typing import Optional

from .fetcher import (
    DataFetcher,
    http_get,
    http_get_json,
    build_cls_params,
    normalize_title,
)

logger = logging.getLogger(__name__)

# ── 通用 HTML 解析工具 ──────────────────────────────────────────

def _extract_news_from_html(html: str, item_pattern: str = None) -> list:
    """从 HTML 中提取新闻标题和时间。使用多种后备模式。"""
    items = []

    # 模式1: <a> 标签含 href 和 title
    for m in re.finditer(r'<a[^>]*href="([^"]*)"[^>]*>([^<]{8,})</a>', html):
        url, title = m.group(1), m.group(2).strip()
        title = re.sub(r'<[^>]+>', '', title).strip()
        if len(title) >= 8 and not title.startswith("<"):
            items.append({"title": normalize_title(title), "url": url, "source": ""})

    if len(items) < 3:
        # 模式2: <h> 标签中的标题
        for m in re.finditer(r'<h\d[^>]*>\s*<a[^>]*href="([^"]*)"[^>]*>([^<]+)</a>', html):
            items.append({
                "title": normalize_title(m.group(2)),
                "url": m.group(1),
                "source": "",
            })

    return items


# ── 1. 财联社电报 ──────────────────────────────────────────────

CLS_API_CANDIDATES = [
    "https://www.cls.cn/v1/roll/get_roll_list",
]
CLS_TELEGRAPH_URL = "https://www.cls.cn/telegraph"
CLS_REFERER = "https://www.cls.cn/"


class ClsTelegraphSource:
    """财联社 7×24 电报。"""

    def __init__(self, top_n: int = 10):
        self.top_n = top_n

    def fetch(self) -> list[dict]:
        """返回电报条目列表。先尝试 API，失败回退 HTML。"""
        items = []

        # ── 方案 A: JSON API ──
        for api_url in CLS_API_CANDIDATES:
            try:
                params = build_cls_params(last_time="", rn=self.top_n)
                data = http_get_json(api_url, referer=CLS_REFERER,
                                     params=params, timeout=15, retries=1)
                if not data:
                    continue

                roll_data = data.get("data", {}).get("roll_data", [])
                if not roll_data:
                    roll_data = data.get("roll_data", [])
                if not roll_data:
                    continue

                for entry in roll_data[:self.top_n]:
                    title = entry.get("title", "")
                    content = entry.get("content", "")
                    brief = entry.get("brief", "")
                    ctime = entry.get("ctime", 0)
                    display_title = title or brief or (content[:60] if content else "")
                    items.append({
                        "title": normalize_title(display_title),
                        "summary": content[:300] if content else brief,
                        "time": datetime.fromtimestamp(ctime).strftime("%H:%M") if ctime else "",
                        "level": entry.get("level", ""),
                        "source": "财联社",
                    })
                if items:
                    return items
            except Exception:
                continue

        # ── 方案 B: HTML 回退 ──
        try:
            html = http_get(CLS_TELEGRAPH_URL, referer=CLS_REFERER,
                            encoding="utf-8", timeout=15, retries=1)
            if html:
                for m in re.finditer(
                    r'<div[^>]*class="[^"]*telegraph-content-box[^"]*"[^>]*>'
                    r'(.{20,300}?)</div>',
                    html, re.DOTALL
                ):
                    title = normalize_title(re.sub(r'<[^>]+>', '', m.group(1)))
                    if len(title) >= 10:
                        items.append({
                            "title": title[:100],
                            "summary": title[:300],
                            "time": "",
                            "level": "",
                            "source": "财联社",
                        })
                        if len(items) >= self.top_n:
                            break

                # 更宽松的回退
                if not items:
                    for m in re.finditer(
                        r'class="[^"]*(?:title|content|brief)[^"]*"[^>]*>'
                        r'(.{15,200}?)</(?:div|span|a)>',
                        html, re.DOTALL
                    ):
                        title = normalize_title(re.sub(r'<[^>]+>', '', m.group(1)))
                        if len(title) >= 10:
                            items.append({
                                "title": title[:100],
                                "summary": "",
                                "time": "",
                                "level": "",
                                "source": "财联社",
                            })
                            if len(items) >= self.top_n:
                                break
        except Exception as e:
            logger.warning("财联社 HTML 回退也失败: %s", e)

        return items


# ── 2. 证券时报 ────────────────────────────────────────────────

STCN_NEWS_URL = "https://news.stcn.com/xwyw/"
STCN_REFERER = "https://www.stcn.com/"


class StcnNewsSource:
    """证券时报新闻。"""

    def __init__(self, top_n: int = 5):
        self.top_n = top_n

    def fetch(self) -> list[dict]:
        """返回证券时报新闻列表。"""
        items = []
        try:
            html = http_get(STCN_NEWS_URL, referer=STCN_REFERER,
                            encoding="utf-8", timeout=15, retries=2)
            if not html:
                return items

            # 提取新闻块：标题链接 + 时间
            # 证券时报结构：<div class="news-list"> 内含 <a> 链接
            for m in re.finditer(
                r'<a[^>]*href="(/[^"]*\d{4,}[^"]*)"[^>]*>\s*(.{10,80}?)\s*</a>',
                html
            ):
                href, title = m.group(1), m.group(2)
                title = normalize_title(re.sub(r'<[^>]+>', '', title))
                if len(title) >= 10:
                    url = href if href.startswith("http") else f"https://news.stcn.com{href}"
                    items.append({
                        "title": title,
                        "summary": "",
                        "time": "",
                        "source": "证券时报",
                        "url": url,
                    })

            # 尝试提取时间
            time_pattern = re.compile(r'(\d{4}-\d{2}-\d{2}\s*\d{2}:\d{2})|(\d{2}:\d{2})')
            times = time_pattern.findall(html)
            for i, item in enumerate(items[:len(times)]):
                t = times[i][0] or times[i][1]
                item["time"] = t

        except Exception as e:
            logger.warning("证券时报抓取失败: %s", e)

        return items[:self.top_n]


# ── 3. 新华财经（中国金融信息网）────────────────────────────────

CNFIN_URL = "https://www.cnfin.com/"
CNFIN_REFERER = "https://www.cnfin.com/"


class CnfinNewsSource:
    """新华财经新闻。尝试 API 端点，失败回退 HTML。"""

    # 可能的内部 API 端点
    API_CANDIDATES = [
        "https://www.cnfin.com/api/news/list?page=1&size=20",
        "https://api.cnfin.com/news/list?page=1&size=20",
    ]

    def __init__(self, top_n: int = 5):
        self.top_n = top_n

    def fetch(self) -> list[dict]:
        """返回新华财经新闻列表。"""
        items = []

        # 优先尝试内部 API
        for api_url in self.API_CANDIDATES:
            data = http_get_json(api_url, referer=CNFIN_REFERER, timeout=10, retries=1)
            if data:
                news_list = data.get("data", data.get("list", data.get("rows", [])))
                if isinstance(news_list, list):
                    for entry in news_list[:self.top_n]:
                        items.append({
                            "title": normalize_title(
                                entry.get("title", entry.get("name", ""))
                            ),
                            "summary": str(entry.get("summary", entry.get("abstract", "")))[:200],
                            "time": str(entry.get("publishTime", entry.get("time", ""))),
                            "source": "新华财经",
                        })
                    if items:
                        return items

        # 回退 HTML 抓取
        try:
            html = http_get(CNFIN_URL, referer=CNFIN_REFERER,
                            encoding="utf-8", timeout=15, retries=2)
            if html:
                # 标准新闻列表模式
                for m in re.finditer(
                    r'<a[^>]*href="([^"]*)"[^>]*>\s*(.{12,100}?)\s*</a>',
                    html
                ):
                    title = normalize_title(re.sub(r'<[^>]+>', '', m.group(2)))
                    if len(title) >= 8 and any(kw in title for kw in
                                               ["金融", "经济", "政策", "市场", "银行", "央行",
                                                "监管", "改革", "宏观", "A股", "利率", "债券"]):
                        items.append({
                            "title": title,
                            "summary": "",
                            "time": "",
                            "source": "新华财经",
                        })
                        if len(items) >= self.top_n:
                            break
        except Exception as e:
            logger.warning("新华财经抓取失败: %s", e)

        return items[:self.top_n]


# ── 4. 界面新闻·财经 ──────────────────────────────────────────

JIEMIAN_URLS = [
    "https://www.jiemian.com/lists/4.html",     # 财经频道
    "https://www.jiemian.com/lists/8.html",     # 宏观频道
]
JIEMIAN_REFERER = "https://www.jiemian.com/"


class JiemianNewsSource:
    """界面新闻财经频道。"""

    def __init__(self, top_n: int = 5):
        self.top_n = top_n

    def fetch(self) -> list[dict]:
        """返回界面新闻列表。"""
        items = []
        for url in JIEMIAN_URLS:
            if len(items) >= self.top_n:
                break
            try:
                html = http_get(url, referer=JIEMIAN_REFERER,
                                encoding="utf-8", timeout=15, retries=1)
                if not html:
                    continue

                # 界面新闻结构：newsflash-item 卡片
                # <div class="...newsflash-item">
                #   <div class="...newsflash-date-node">时间</div>
                #   <div class="...newsflash-content">
                #     <h4><a href="...">标题</a></h4>
                #     <div class="...summary">摘要</div>
                for m in re.finditer(
                    r'newsflash-date-node[^>]*>([^<]*)</div>.*?'
                    r'<a[^>]*href="(/article/\d+[^"]*)"[^>]*>'
                    r'\s*(.{12,150}?)\s*</a>',
                    html, re.DOTALL
                ):
                    time_str = m.group(1).strip()
                    title = normalize_title(re.sub(r'<[^>]+>', '', m.group(3)))
                    if len(title) >= 8:
                        items.append({
                            "title": title,
                            "summary": "",
                            "time": time_str,
                            "source": "界面新闻",
                        })

                # 回退：匹配任何 article 链接
                if not items:
                    for m in re.finditer(
                        r'<a[^>]*href="(/article/\d+[^"]*)"[^>]*>'
                        r'\s*(.{12,150}?)\s*</a>',
                        html, re.DOTALL
                    ):
                        title = normalize_title(re.sub(r'<[^>]+>', '', m.group(2)))
                        if len(title) >= 10 and len(title) < 120:
                            items.append({
                                "title": title,
                                "summary": "",
                                "time": "",
                                "source": "界面新闻",
                            })

            except Exception as e:
                logger.warning("界面新闻 %s 抓取失败: %s", url, e)

        return items[:self.top_n]


# ── 新闻聚合器 ──────────────────────────────────────────────────

class NewsDataFetcher(DataFetcher):
    """多源新闻聚合器 —— 依次抓取四个来源，合并去重。"""

    def __init__(self, top_n: int = 10, delay: float = 1.5):
        super().__init__(delay=delay)
        self.top_n = top_n
        self.sources = [
            ClsTelegraphSource(top_n=top_n),
            StcnNewsSource(top_n=top_n),
            CnfinNewsSource(top_n=top_n),
            JiemianNewsSource(top_n=top_n),
        ]

    def fetch(self) -> dict:
        """抓取所有源并合并。"""
        all_items = []
        source_stats = {}

        for src in self.sources:
            src_name = src.__class__.__name__
            try:
                items = src.fetch()
                source_stats[src_name] = len(items)
                all_items.extend(items)
                time.sleep(0.8)  # 源间间隔
            except Exception as e:
                logger.warning("%s 完全失败: %s", src_name, e)
                source_stats[src_name] = 0

        # 去重（按标题相似度）
        deduped = self._deduplicate(all_items)

        # 按时间排序：有时间戳的优先
        result = {
            "eastmoney_news": [],   # 保持兼容旧结构
            "cls_news": [],
            "all_news": deduped[:self.top_n],
            "source_stats": source_stats,
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

        # 按来源分类填充（兼容旧 prompt 格式）
        for item in deduped:
            entry = {
                "title": item["title"],
                "summary": item.get("summary", ""),
                "time": item.get("time", ""),
            }
            if item["source"] == "财联社":
                result["cls_news"].append(entry)
            else:
                result["eastmoney_news"].append(entry)

        return result

    def _deduplicate(self, items: list) -> list:
        """按标题相似度去重。"""
        seen = set()
        result = []
        for item in items:
            # 取前 15 个字符做简易指纹
            key = item["title"][:15]
            if key not in seen:
                seen.add(key)
                result.append(item)
        return result

    def get_news_summary(self, data: Optional[dict] = None) -> list:
        """获取新闻摘要列表，按来源标注。"""
        if data is None:
            data = self.safe_fetch() or {}
        items = []
        for n in data.get("all_news", []):
            items.append(f"[{n['source']}] {n['title']}")
        return items


# ── 快照格式化 ──────────────────────────────────────────────────

def format_news_snapshot(data: dict) -> str:
    """将新闻数据格式化为 Markdown。"""
    if data is None:
        data = {}
    lines = ["## 今日财经快讯",
             f"抓取时间：{data.get('fetched_at', '')}",
             f"数据来源：财联社 / 证券时报 / 新华财经 / 界面新闻",
             ""]

    stats = data.get("source_stats", {})
    if stats:
        lines.append("### 各源抓取统计")
        for name, count in stats.items():
            lines.append(f"- {name}: {count} 条")
        lines.append("")

    lines.append("### 新闻列表")
    for n in data.get("all_news", []):
        time_str = f" ({n['time']})" if n.get("time") else ""
        lines.append(f"- **[{n['source']}]{time_str}** {n['title']}")
        if n.get("summary"):
            lines.append(f"  {n['summary'][:150]}")

    if not data.get("all_news"):
        lines.append("（今日暂无重要快讯，请关注后续更新）")

    lines.append("")
    return "\n".join(lines)
