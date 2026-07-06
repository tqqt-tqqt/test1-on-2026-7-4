"""每日运行编排器 —— 数据采集 → 文案生成 → 配图 → 保存。"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..data.market_data import MarketDataFetcher, format_market_snapshot
from ..data.news_data import NewsDataFetcher, format_news_snapshot
from ..data.ipo_data import IPODataFetcher, format_ipo_snapshot
from ..generator.prompt_builder import (
    get_prompt,
    CATEGORY_NAMES,
    CATEGORY_EMOJI,
)
from ..generator.llm_client import generate_copy_with_fallback
from ..generator.image_generator import build_image_prompt, generate_image
from ..output.file_manager import (
    get_output_dir,
    save_copy,
    save_snapshot,
    save_summary,
)

logger = logging.getLogger(__name__)

# 非交易日仍可生成的内容分类
NON_TRADING_CATEGORIES = {"投顾服务", "投资者教育"}


def fetch_all_data(config: dict) -> dict:
    """并行采集所有数据源（实际串行，a 股数据源有依赖）。"""
    data_cfg = config.get("data", {})
    top_n = data_cfg.get("top_sectors_count", 5)
    indices = data_cfg.get("indices", ["000001", "399001", "399006"])
    top_news = data_cfg.get("top_news_count", 5)
    delay = 1.5

    logger.info("开始采集市场数据...")

    market_fetcher = MarketDataFetcher(indices=indices, top_n=top_n, delay=delay)
    news_fetcher = NewsDataFetcher(top_n=top_news, delay=delay)
    ipo_fetcher = IPODataFetcher(top_n=top_n, delay=delay)

    market_data = market_fetcher.safe_fetch()
    news_data = news_fetcher.safe_fetch()
    ipo_data = ipo_fetcher.safe_fetch()

    has_market_data = market_data and len(market_data.get("indices", [])) > 0

    return {
        "market_data": market_data,
        "news_data": news_data,
        "ipo_data": ipo_data,
        "is_trading_day": has_market_data,
    }


def build_fallback_text(category: str, data: dict, config: dict, date_str: str) -> str:
    """LLM 失败时，用真实数据构建回退文案。"""
    hashtags = " ".join(f"#{tag}" for tag in config.get("hashtags", []))
    emoji = CATEGORY_EMOJI.get(category, "📌")
    market = data.get("market_data") or {}
    indices = market.get("indices", [])

    parts = [f"{emoji} 【{date_str}】{category}"]
    parts.append("")

    if indices:
        idx_str = " | ".join(
            f"{i['name']}: {i['price']}（{i['change_pct']:+.2f}%）"
            for i in indices[:3]
        )
        parts.append(f"今日市场：{idx_str}")
    else:
        parts.append("今日券商营业部日常分享。")

    parts.append("")
    parts.append(f"关注我们，了解更多{category}相关内容。")
    parts.append(
        "⚠️ 风险提示：市场有风险，投资需谨慎。本文仅为资讯分享，不构成投资建议。"
    )
    parts.append(hashtags)
    return "\n".join(parts)


def run_daily(
    config_path: str = "config.json",
    date_str: str = None,
    dry_run: bool = False,
) -> dict:
    """执行每日编排流程。

    Args:
        config_path: 配置文件路径
        date_str: 日期字符串（YYYY-MM-DD），默认今天
        dry_run: 仅输出到控制台不保存文件

    Returns:
        运行结果摘要
    """
    import json

    # 加载配置
    config_path = Path(config_path)
    if config_path.exists():
        config = json.loads(config_path.read_text(encoding="utf-8"))
    else:
        config = {}

    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")

    logger.info("═══ 开始 %s 小红书文案生成 ═══", date_str)

    # 1. 数据采集
    data = fetch_all_data(config)
    is_trading = data["is_trading_day"]
    logger.info("数据采集完成 | 交易日: %s", "是" if is_trading else "否（或数据不可用）")

    # 2. 保存数据快照
    output_dir = get_output_dir(config.get("output_dir", "output"), date_str)
    if not dry_run:
        snapshot = format_market_snapshot(data["market_data"] or {})
        snapshot += "\n" + format_news_snapshot(data["news_data"] or {})
        from ..data.ipo_data import format_ipo_snapshot
        snapshot += "\n" + format_ipo_snapshot(data["ipo_data"] or {})
        save_snapshot(snapshot, output_dir)
        logger.info("市场数据快照已保存")

    # 3. 确定要生成的分类
    schedule_cfg = config.get("schedule", {})
    enabled = schedule_cfg.get("enabled_categories", list(CATEGORY_NAMES.keys()))
    if not is_trading:
        enabled = [c for c in enabled if c in NON_TRADING_CATEGORIES]
        logger.info("非交易日，仅生成: %s", "、".join(enabled))

    gen_cfg = config.get("generation", {})
    model = config.get("model", "gpt-4o-mini")
    img_cfg = config.get("image", {})
    img_enabled = img_cfg.get("enabled", False)

    # 4. 逐个分类生成文案
    copy_results = []

    for category in enabled:
        logger.info("生成中: %s ...", category)
        key = CATEGORY_NAMES.get(category, category)

        try:
            prompt = get_prompt(
                category=category,
                market_data=data["market_data"],
                news_data=data["news_data"],
                ipo_data=data["ipo_data"],
                config=config,
                date_str=date_str,
            )

            fallback = build_fallback_text(category, data, config, date_str)
            text = generate_copy_with_fallback(
                prompt=prompt,
                model=model,
                fallback_text=fallback,
                temperature=gen_cfg.get("temperature", 0.8),
                max_tokens=gen_cfg.get("max_tokens", 700),
                retry_count=gen_cfg.get("retry_count", 3),
                retry_delay=gen_cfg.get("retry_delay_seconds", 5),
            )

            if dry_run:
                print(f"\n{'='*50}")
                print(f"  {CATEGORY_EMOJI.get(category, '')} {category}")
                print(f"{'='*50}")
                print(text)
                copy_results.append({"category": category, "success": True, "file": "(dry-run)"})
            else:
                file_path = save_copy(text, output_dir, key)
                copy_results.append({"category": category, "success": True, "file": str(file_path)})
                logger.info("  已保存: %s", file_path)

        except Exception as exc:
            logger.error("  %s 生成失败: %s", category, exc)
            copy_results.append({"category": category, "success": False, "error": str(exc)})

    # 5. 生成配图（可选）
    image_results = []
    if img_enabled and not dry_run:
        logger.info("开始生成配图...")
        img_output_dir = output_dir / "images"
        for r in copy_results:
            if not r["success"]:
                continue
            category = r["category"]
            key = CATEGORY_NAMES.get(category, category)
            # 读取已保存的文案来生成图片提示词
            copy_file = output_dir / f"{key}.md"
            if copy_file.exists():
                copy_text = copy_file.read_text(encoding="utf-8")
                img_prompt = build_image_prompt(category, copy_text)
                img_path = generate_image(
                    prompt=img_prompt,
                    output_path=img_output_dir / key,
                    model=img_cfg.get("model", "dall-e-3"),
                    size=img_cfg.get("size", "1024x1024"),
                    style=img_cfg.get("style", "vivid"),
                )
                image_results.append({"category": category, "path": str(img_path) if img_path else None})
                time.sleep(2)  # DALL-E 速率限制

    # 6. 保存运行摘要
    if not dry_run:
        summary_path = save_summary(output_dir, date_str, copy_results, image_results)
        logger.info("运行摘要已保存: %s", summary_path)

    success_count = sum(1 for r in copy_results if r["success"])
    logger.info("═══ 完成！生成 %d/%d 篇文案 ═══", success_count, len(copy_results))

    return {
        "date": date_str,
        "is_trading_day": is_trading,
        "total": len(copy_results),
        "success": success_count,
        "results": copy_results,
        "images": image_results,
        "output_dir": str(output_dir) if not dry_run else "(dry-run)",
    }
