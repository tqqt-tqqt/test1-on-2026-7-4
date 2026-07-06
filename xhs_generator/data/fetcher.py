"""数据采集基类与工具函数。"""

import time
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)


class DataFetcher(ABC):
    """数据采集器抽象基类。"""

    def __init__(self, delay: float = 2.0):
        self.delay = delay

    def safe_fetch(self) -> Optional[dict]:
        """安全抓取数据，捕获异常后返回 None。"""
        try:
            time.sleep(self.delay)  # 避免请求过快被限流
            return self.fetch()
        except Exception as exc:
            logger.warning("%s 抓取失败: %s", self.__class__.__name__, exc)
            return None

    @abstractmethod
    def fetch(self) -> dict:
        """子类实现具体抓取逻辑。"""
        ...


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
