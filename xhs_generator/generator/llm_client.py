"""OpenAI LLM 客户端封装 —— 支持重试和回退。"""

import os
import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def _get_openai_client():
    """延迟导入并返回 OpenAI 客户端。"""
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError(
            "无法导入 openai，请先运行 `pip install -r requirements.txt`。"
        )

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("请设置环境变量 OPENAI_API_KEY")

    base_url = os.getenv("OPENAI_BASE_URL")
    kwargs = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def generate_copy(
    prompt: str,
    model: str = "gpt-4o-mini",
    system_prompt: str = None,
    temperature: float = 0.8,
    max_tokens: int = 700,
    retry_count: int = 3,
    retry_delay: float = 5.0,
) -> str:
    """调用 LLM 生成文案，支持重试。

    Args:
        prompt: 用户提示词
        model: 模型名称
        system_prompt: 系统提示词
        temperature: 温度参数
        max_tokens: 最大 token 数
        retry_count: 重试次数
        retry_delay: 重试间隔（秒）

    Returns:
        生成的文案文本

    Raises:
        RuntimeError: 所有重试都失败时抛出
    """
    if system_prompt is None:
        system_prompt = "你是一个擅长撰写券商营业部日常小红书运营文案的中文创作者。"

    client = _get_openai_client()
    last_error = None

    for attempt in range(1, retry_count + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            last_error = exc
            logger.warning("LLM 调用失败 (第 %d/%d 次): %s", attempt, retry_count, exc)
            if attempt < retry_count:
                time.sleep(retry_delay * attempt)  # 指数退避
            continue

    raise RuntimeError(f"LLM 调用在 {retry_count} 次重试后仍然失败: {last_error}")


def generate_copy_with_fallback(
    prompt: str,
    model: str = "gpt-4o-mini",
    fallback_text: str = "",
    **kwargs,
) -> str:
    """生成文案，失败时返回回退文本。"""
    try:
        return generate_copy(prompt, model=model, **kwargs)
    except Exception as exc:
        logger.error("文案生成失败，使用回退文本: %s", exc)
        return fallback_text
