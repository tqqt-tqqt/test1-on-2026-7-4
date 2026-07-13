"""LLM 客户端封装 —— OpenAI 兼容接口 + JSON 解析。"""

import json
import os
import re
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


def _extract_json(text: str) -> Optional[dict]:
    """从 LLM 返回文本中提取 JSON 对象。

    依次尝试：直接解析 → 提取 ```json 代码块 → 提取 { } 块。
    """
    if not text:
        return None

    # 1. 直接解析
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        pass

    # 2. 提取 ```json ... ``` 代码块
    m = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 3. 提取第一个 { ... } 块
    m = re.search(r'\{[\s\S]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    return None


def generate_copy(
    prompt: str,
    model: str = "deepseek-v4-flash",
    system_prompt: str = None,
    temperature: float = 0.8,
    max_tokens: int = 2000,
    retry_count: int = 3,
    retry_delay: float = 5.0,
) -> str:
    """调用 LLM 生成文案，支持重试。

    Returns:
        生成的原始文本
    """
    if system_prompt is None:
        system_prompt = (
            "你是一个擅长撰写券商营业部小红书运营文案的中文创作者。"
            "你总是严格按照要求的 JSON 格式输出，不输出任何额外内容。"
        )

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
                time.sleep(retry_delay * attempt)
            continue

    raise RuntimeError(f"LLM 调用在 {retry_count} 次重试后仍然失败: {last_error}")


def generate_structured(
    prompt: str,
    model: str = "deepseek-v4-flash",
    temperature: float = 0.8,
    max_tokens: int = 2000,
    retry_count: int = 3,
    retry_delay: float = 5.0,
) -> dict:
    """调用 LLM 生成结构化 JSON 文案。

    Returns:
        解析后的 dict，包含 title、body、image_texts、tags
        解析失败时返回错误 dict（含 error 字段）
    """
    system_prompt = (
        "你是一个擅长撰写券商营业部小红书运营文案的中文创作者。"
        "你总是严格按照要求的 JSON 格式输出，不输出任何额外内容。"
        "你的回复必须是纯粹的 JSON 对象，没有解释、没有 markdown 标记、没有前缀。"
    )

    try:
        raw = generate_copy(
            prompt=prompt,
            model=model,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            retry_count=retry_count,
            retry_delay=retry_delay,
        )
    except Exception as exc:
        return {"error": str(exc), "raw": ""}

    result = _extract_json(raw)
    if result is None:
        logger.warning("JSON 解析失败，原始返回: %s", raw[:300])
        return {"error": "JSON 解析失败", "raw": raw}

    # 确保必有字段存在
    for key in ["title", "body", "image_texts", "tags"]:
        if key not in result:
            result[key] = "" if key != "image_texts" else []
            if key == "tags":
                result[key] = []

    return result


def generate_copy_with_fallback(
    prompt: str,
    model: str = "deepseek-v4-flash",
    fallback_text: str = "",
    **kwargs,
) -> str:
    """生成文案，失败时返回回退文本。"""
    try:
        return generate_copy(prompt, model=model, **kwargs)
    except Exception as exc:
        logger.error("文案生成失败，使用回退文本: %s", exc)
        return fallback_text
