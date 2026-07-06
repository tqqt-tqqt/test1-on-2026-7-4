"""DALL-E 配图生成。"""

import os
import time
import logging
from pathlib import Path
from typing import Optional
from base64 import b64decode

logger = logging.getLogger(__name__)


def _get_openai_client():
    """延迟导入并返回 OpenAI 客户端。"""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("无法导入 openai，请先运行 `pip install -r requirements.txt`。")

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 OPENAI_API_KEY")

    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def build_image_prompt(category: str, copy_text: str) -> str:
    """根据文案内容和分类构建图片生成提示词。

    小红书封面图风格：简洁、有设计感、商务但不沉闷。
    """
    category_keywords = {
        "市场热点": "金融图表、K线、股票走势、红色绿色、数据可视化",
        "新闻动态": "报纸、新闻、报纸堆叠、财经头条、手机推送通知",
        "IPO": "敲钟仪式、上市庆典、交易所大楼、金色、庆祝",
        "投顾服务": "商务人士、办公桌、专业顾问、握手、简洁商务风",
        "投资者教育": "书籍、黑板、灯泡、学习、成长、图表教学",
        "每日精选": "每日摘要、日历、咖啡、晨间阅读、简约生活",
    }

    kws = category_keywords.get(category, "金融、投资、股票、商务简洁风")
    # 取文案前 100 字作为画面描述参考
    excerpt = copy_text[:100].replace("\n", " ")

    return (
        f"A Xiaohongshu (RED) style cover image for a finance/investment post. "
        f"Theme: {category}. Visual elements: {kws}. "
        f"Post excerpt context: {excerpt}. "
        f"Style: clean, modern, soft warm lighting, minimalist composition, "
        f"pastel accent colors, suitable for a lifestyle-social-media aesthetic "
        f"but with professional finance tone. No text on the image. "
        f"Aspect ratio: square 1:1."
    )


def generate_image(
    prompt: str,
    output_path: Path,
    model: str = "dall-e-3",
    size: str = "1024x1024",
    style: str = "vivid",
    retry_count: int = 2,
) -> Optional[Path]:
    """生成一张图片并保存到指定路径。

    Args:
        prompt: DALL-E 图片生成提示词
        output_path: 输出文件路径（不含扩展名，自动加 .png）
        model: DALL-E 模型
        size: 图片尺寸
        style: vivid 或 natural
        retry_count: 重试次数

    Returns:
        保存的图片路径，失败返回 None
    """
    client = _get_openai_client()
    output_path = output_path.with_suffix(".png")

    for attempt in range(1, retry_count + 1):
        try:
            response = client.images.generate(
                model=model,
                prompt=prompt,
                size=size,
                quality="standard",
                style=style,
                n=1,
            )

            # DALL-E 3 返回 URL 或 b64_json
            image_data = response.data[0]
            if image_data.b64_json:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(b64decode(image_data.b64_json))
            elif image_data.url:
                import urllib.request
                output_path.parent.mkdir(parents=True, exist_ok=True)
                urllib.request.urlretrieve(image_data.url, str(output_path))
            else:
                logger.warning("DALL-E 返回无图片数据")
                return None

            logger.info("配图已生成: %s", output_path)
            return output_path

        except Exception as exc:
            logger.warning("图片生成失败 (第 %d/%d 次): %s", attempt, retry_count, exc)
            if attempt < retry_count:
                time.sleep(5)
            continue

    logger.error("图片生成在 %d 次重试后仍然失败", retry_count)
    return None
