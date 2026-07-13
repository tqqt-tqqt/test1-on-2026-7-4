"""每日运行编排器 —— 数据采集 → JSON 文案生成 → 配图 → 保存。"""

import json as json_mod
import logging
import re
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
    BROKERAGE_SIGNATURE,
)
from ..generator.llm_client import generate_structured
from ..generator.image_generator import build_image_prompt, generate_image
from ..output.file_manager import (
    get_output_dir,
    save_post,
    save_snapshot,
    save_summary,
)

logger = logging.getLogger(__name__)

NON_TRADING_CATEGORIES = {"投顾服务", "投资者教育"}


def fetch_all_data(config: dict) -> dict:
    """采集所有数据源。"""
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

    indices = market_data.get("indices", []) if market_data else []
    is_trading = (
        len(indices) > 0
        and not all(abs(idx.get("change_pct", 0)) < 0.01 for idx in indices)
    )

    return {
        "market_data": market_data,
        "news_data": news_data,
        "ipo_data": ipo_data,
        "is_trading_day": is_trading,
    }


def _safe_label(category: str) -> str:
    """Windows 终端安全的分类标签。"""
    labels = {
        "市场热点": "[热点]", "新闻动态": "[新闻]", "IPO": "[IPO]",
        "投顾服务": "[投顾]", "投资者教育": "[投教]", "每日精选": "[精选]",
    }
    return labels.get(category, "")


def build_fallback_post(category: str, data: dict, config: dict, date_str: str) -> dict:
    """LLM 失败时用真实数据构建回退 JSON。"""
    hashtags = config.get("hashtags", [])
    market = data.get("market_data") or {}
    indices = market.get("indices", [])

    # 构建标题
    title = f"今日{category}速递"

    # 构建正文
    body_parts = [f"【{date_str}】券商营业部今日{category}分享", ""]
    if indices:
        idx_str = " | ".join(
            f"{i['name']}: {i['price']}（{i['change_pct']:+.2f}%）"
            for i in indices[:3]
        )
        body_parts.append(f"今日市场概况：{idx_str}")
    else:
        body_parts.append("今日券商营业部日常分享。")
    body_parts.append("")
    body_parts.append(f"关注我们，了解更多{category}相关内容。")
    body_parts.append("")
    body_parts.append("⚠️ 风险提示：市场有风险，投资需谨慎。本文仅为资讯分享，不构成投资建议。")
    body_parts.append("")
    body_parts.append(BROKERAGE_SIGNATURE)

    # 图片文字（1页）
    intro = f"【{category}】{date_str}" + (" | " + indices[0]['name'] + " " + str(indices[0]['price']) if indices else "")
    img_texts = [intro + "\n\n" + f"今日{category}要点速览，关注我们了解更多。"]

    # 标签
    all_tags = [f"#{t}" for t in hashtags] + [f"#{category}", "#理财", "#投资", "#财经",
                                                "#A股", "#股票", "#投教", "#每日复盘",
                                                "#券商", "#金融知识", "#小白理财"]
    # 去重
    seen = set()
    tags = []
    for t in all_tags:
        if t not in seen:
            seen.add(t)
            tags.append(t)

    return {"title": title, "body": "\n".join(body_parts), "image_texts": img_texts, "tags": tags[:15]}


def _count_chinese(text: str) -> int:
    """统计中文字符数。"""
    return len(re.findall(r'[一-鿿]', text))


def run_daily(
    config_path: str = "config.json",
    date_str: str = None,
    dry_run: bool = False,
) -> dict:
    """执行每日编排流程。"""
    config_path = Path(config_path)
    if config_path.exists():
        config = json_mod.loads(config_path.read_text(encoding="utf-8"))
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
        snapshot += "\n" + format_ipo_snapshot(data["ipo_data"] or {})
        save_snapshot(snapshot, output_dir)
        logger.info("市场数据快照已保存")

    # 3. 确定分类
    schedule_cfg = config.get("schedule", {})
    enabled = schedule_cfg.get("enabled_categories", list(CATEGORY_NAMES.keys()))
    if not is_trading:
        enabled = [c for c in enabled if c in NON_TRADING_CATEGORIES]
        logger.info("非交易日，仅生成: %s", "、".join(enabled))

    gen_cfg = config.get("generation", {})
    model = config.get("model", "deepseek-v4-flash")
    img_cfg = config.get("image", {})
    img_enabled = img_cfg.get("enabled", False)

    # 4. 逐个分类生成
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

            result = generate_structured(
                prompt=prompt,
                model=model,
                temperature=gen_cfg.get("temperature", 0.8),
                max_tokens=gen_cfg.get("max_tokens", 2000),
                retry_count=gen_cfg.get("retry_count", 3),
                retry_delay=gen_cfg.get("retry_delay_seconds", 5),
            )

            if result.get("error"):
                logger.warning("结构化生成失败: %s，使用回退数据", result["error"])
                result = build_fallback_post(category, data, config, date_str)

            # 质量检查
            title = str(result.get("title", "")).strip()
            if len(title) > 25:
                title = title[:25]  # 截断过长标题

            body = str(result.get("body", ""))
            img_texts = result.get("image_texts", [])
            if isinstance(img_texts, str):
                img_texts = [img_texts]
            img_texts = [str(t) for t in img_texts[:3]]
            tags = result.get("tags", [])
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.replace("#", " #").split() if t.strip()]
            tags = [t if t.startswith("#") else f"#{t}" for t in tags[:18]]

            if dry_run:
                _print_result(category, title, body, img_texts, tags)
                copy_results.append({"category": category, "success": True, "file": "(dry-run)"})
            else:
                file_path = save_post(output_dir, key, title, body, img_texts, tags)
                copy_results.append({"category": category, "success": True, "file": str(file_path)})
                logger.info("  已保存: %s", file_path)

        except Exception as exc:
            logger.error("  %s 生成失败: %s", category, exc)
            copy_results.append({"category": category, "success": False, "error": str(exc)})

    # 5. 配图
    image_results = []
    if img_enabled and not dry_run:
        logger.info("开始生成配图...")
        img_output_dir = output_dir / "images"
        for r in copy_results:
            if not r["success"]:
                continue
            category = r["category"]
            key = CATEGORY_NAMES.get(category, category)
            copy_file = output_dir / f"{key}.md"
            if copy_file.exists():
                body_text = copy_file.read_text(encoding="utf-8")
                img_prompt = build_image_prompt(category, body_text[:500])
                img_path = generate_image(
                    prompt=img_prompt,
                    output_path=img_output_dir / key,
                    model=img_cfg.get("model", "dall-e-3"),
                    size=img_cfg.get("size", "1024x1024"),
                    style=img_cfg.get("style", "vivid"),
                )
                image_results.append({"category": category, "path": str(img_path) if img_path else None})
                time.sleep(2)

    # 6. 摘要
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


def _print_result(category: str, title: str, body: str, img_texts: list, tags: list):
    """打印结果到控制台（无 emoji，Windows 终端兼容）。"""
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"  {_safe_label(category)} {category}")
    print(sep)
    print(f"\n[标题] ({len(title)}字): {title}")
    print(f"\n-- 正文 ({_count_chinese(body)}字) --")
    # 截取前 500 字符显示
    display_body = body[:500] + ("..." if len(body) > 500 else "")
    # 过滤 emoji 以免 GBK 终端报错
    display_body = display_body.encode("gbk", errors="replace").decode("gbk", errors="replace")
    print(display_body)
    print(f"\n-- 图片文字 ({len(img_texts)}页) --")
    for i, t in enumerate(img_texts, 1):
        safe_t = t[:120].encode("gbk", errors="replace").decode("gbk", errors="replace")
        print(f"  第{i}页 ({_count_chinese(t)}字): {safe_t}...")
    print(f"\n-- 标签 ({len(tags)}个) --")
    tag_str = " ".join(tags).encode("gbk", errors="replace").decode("gbk", errors="replace")
    print("  " + tag_str)
    print()
