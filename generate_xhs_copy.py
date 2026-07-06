#!/usr/bin/env python3
"""
券商营业部小红书文案生成工具。
支持手动单次运行，也可配合 Windows 计划任务每日自动执行。

用法:
  # 每日自动运行（使用真实市场数据生成所有启用分类的文案 + 配图）
  python generate_xhs_copy.py

  # 生成指定分类的单篇文案
  python generate_xhs_copy.py --content-type 市场热点

  # 试运行（仅输出到控制台）
  python generate_xhs_copy.py --dry-run

  # 指定日期
  python generate_xhs_copy.py --date 2026-07-06

  # 守护进程模式（每天定时运行）
  python generate_xhs_copy.py --daemon --time 16:00
"""

import argparse
import json
import logging
from datetime import datetime
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore

from xhs_generator.scheduler.daily_runner import run_daily
from xhs_generator.generator.prompt_builder import CATEGORY_NAMES

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "model": "gpt-4o-mini",
    "theme": "券商营业部日常运营",
    "tone": "专业、平实、亲切",
    "hashtags": ["券商", "A股", "投资教育"],
    "length": "150-220字",
    "audience": "有投资需求的年轻用户，关注市场动态和理财教育",
    "output_dir": "output",
    "content_categories": ["市场热点", "新闻动态", "IPO", "投顾服务", "投资者教育"],
}


def load_config(path: Path) -> dict:
    """加载配置，回退到默认值。"""
    if not path.exists():
        return DEFAULT_CONFIG.copy()
    with path.open("r", encoding="utf-8") as f:
        return {**DEFAULT_CONFIG, **json.load(f)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="券商营业部小红书文案生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                                   # 每日全量运行
  %(prog)s --content-type 市场热点            # 只生成市场热点
  %(prog)s --dry-run                         # 试运行（仅输出）
  %(prog)s --daemon --time 16:00             # 守护进程模式
  %(prog)s --no-image                        # 跳过配图生成
        """,
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="配置文件路径（默认 config.json）",
    )
    parser.add_argument(
        "--date",
        default=datetime.now().strftime("%Y-%m-%d"),
        help="目标日期 YYYY-MM-DD（默认今天）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅输出文案到控制台，不保存文件",
    )
    parser.add_argument(
        "--content-type",
        default=None,
        help="手动指定单一内容分类（如: 市场热点、新闻动态、IPO、投顾服务、投资者教育、每日精选）",
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="以守护进程模式运行，每天定时执行",
    )
    parser.add_argument(
        "--time",
        default="16:00",
        help="守护进程模式的每日运行时间（默认 16:00）",
    )
    parser.add_argument(
        "--no-image",
        action="store_true",
        help="关闭配图生成（覆盖 config.json 中的 image.enabled）",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="显示详细日志",
    )
    return parser.parse_args()


def main() -> int:
    # 加载 .env
    if load_dotenv is not None:
        env_path = Path(".env")
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)

    args = parse_args()

    # 日志配置
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s" if args.verbose else "[%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    config_path = Path(args.config)
    config = load_config(config_path)

    # 处理 --content-type 参数：限定为单一分类
    if args.content_type:
        if args.content_type not in CATEGORY_NAMES:
            valid = "、".join(CATEGORY_NAMES.keys())
            print(f"错误：未知分类 '{args.content_type}'，可选：{valid}")
            return 1
        config.setdefault("schedule", {})["enabled_categories"] = [args.content_type]

    # 处理 --no-image
    if args.no_image:
        config.setdefault("image", {})["enabled"] = False

    # 守护进程模式
    if args.daemon:
        from xhs_generator.scheduler.task_scheduler import run_scheduler
        run_scheduler(config_path=str(config_path), run_time=args.time)
        return 0

    # 单次运行
    result = run_daily(
        config_path=str(config_path),
        date_str=args.date,
        dry_run=args.dry_run,
    )

    # 输出汇总
    print(f"\n{'='*50}")
    print(f"  日期: {result['date']} | 交易日: {'是' if result['is_trading_day'] else '否'}")
    print(f"  生成: {result['success']}/{result['total']} 篇成功")
    print(f"  输出: {result['output_dir']}")
    if result.get("images"):
        img_ok = sum(1 for i in result["images"] if i.get("path"))
        print(f"  配图: {img_ok}/{len(result['images'])} 张")
    print(f"{'='*50}")

    return 0 if result["success"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
