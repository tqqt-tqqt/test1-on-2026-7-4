"""数据采集基类 —— HTTP 请求工具、签名、格式化。"""

import hashlib
import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ── HTTP 会话配置 ──────────────────────────────────────────────

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
]

_session: Optional[requests.Session] = None


def get_session() -> requests.Session:
    """获取或创建带通用头的 HTTP 会话。"""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate",
        })
    return _session


def http_get(url: str, referer: str = "", params: dict = None,
             timeout: int = 15, retries: int = 2, encoding: str = None) -> Optional[str]:
    """带重试和通用头的 HTTP GET，返回解码后的文本。"""
    session = get_session()
    headers = {}
    if referer:
        headers["Referer"] = referer

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=headers, params=params,
                               timeout=timeout)
            resp.raise_for_status()
            if encoding:
                resp.encoding = encoding
            return resp.text
        except requests.RequestException as exc:
            logger.warning("HTTP GET 失败 (第 %d/%d 次) %s: %s",
                           attempt, retries, url[:80], exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


def http_get_json(url: str, referer: str = "", params: dict = None,
                  timeout: int = 15, retries: int = 2) -> Optional[dict]:
    """HTTP GET 并解析 JSON。"""
    session = get_session()
    headers = {}
    if referer:
        headers["Referer"] = referer

    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, headers=headers, params=params,
                               timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            logger.warning("HTTP GET JSON 失败 (第 %d/%d 次) %s: %s",
                           attempt, retries, url[:80], exc)
            if attempt < retries:
                time.sleep(2 ** attempt)
    return None


# ── 财联社签名 ─────────────────────────────────────────────────

def _cls_sign(params_str: str) -> str:
    """财联社 API 签名：SHA1(参数字符串) → MD5。"""
    sha1 = hashlib.sha1(params_str.encode()).hexdigest()
    return hashlib.md5(sha1.encode()).hexdigest()


def build_cls_params(last_time: str = "", rn: int = 20) -> dict:
    """构建财联社电报 API 的请求参数（含签名）。"""
    params = {
        "app": "CailianpressWeb",
        "os": "web",
        "sv": "7.7.5",
        "category": "",
        "lastTime": last_time,
        "rn": str(rn),
        "refresh_type": "1",
    }
    # 按字母序拼接
    param_str = "&".join(f"{k}={params[k]}" for k in sorted(params))
    params["sign"] = _cls_sign(param_str)
    return params


# ── 格式化工具 ──────────────────────────────────────────────────

def format_pct(value) -> str:
    """将浮点数格式化为百分比字符串。"""
    if value is None:
        return "N/A"
    return f"{value:+.2f}%"


def format_volume(vol: float) -> str:
    """格式化成交额（亿元）。"""
    if vol is None:
        return "N/A"
    return f"{vol:.2f}亿"


# ── 基类 ────────────────────────────────────────────────────────

class DataFetcher(ABC):
    """数据采集器抽象基类。"""

    def __init__(self, delay: float = 1.0):
        self.delay = delay

    def safe_fetch(self) -> Optional[dict]:
        """安全抓取数据，捕获异常并 jitter 延迟。"""
        try:
            time.sleep(self.delay + random.uniform(0, 0.5))
            return self.fetch()
        except Exception as exc:
            logger.warning("%s 抓取失败: %s", self.__class__.__name__, exc)
            return None

    @abstractmethod
    def fetch(self) -> dict:
        """子类实现具体抓取逻辑。"""
        ...


def normalize_title(title: str) -> str:
    """清理标题中的空白和特殊字符。"""
    return " ".join(str(title).split()).strip()
