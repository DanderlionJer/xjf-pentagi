"""Helpers for OpenAI-compatible chat APIs (OpenAI, DeepSeek, OpenRouter, vLLM, etc.)."""

from __future__ import annotations

import os
from typing import Any


def normalize_openai_compatible_base_url(base_url: str) -> str:
    """Strip slashes and fix common DeepSeek typo: host without /v1 suffix.

    DeepSeek expects requests to ``https://api.deepseek.com/v1/chat/completions``;
    users often paste ``https://api.deepseek.com`` only.
    """
    b = base_url.strip().rstrip("/")
    if not b:
        return b
    low = b.lower()
    if "api.deepseek.com" in low and not low.endswith("/v1"):
        return b + "/v1"
    return b


def resolve_llm_api_key(explicit: str | None = None) -> str:
    """UI / explicit key first, then OpenAI-style env, then DeepSeek env."""
    for candidate in (
        (explicit or "").strip(),
        (os.environ.get("OPENAI_API_KEY") or "").strip(),
        (os.environ.get("DEEPSEEK_API_KEY") or "").strip(),
    ):
        if candidate:
            return candidate
    return ""


def resolve_llm_base_url(explicit: str | None = None) -> str:
    """Resolve base URL (.../v1) from UI or env; default OpenAI if unset."""
    if explicit is not None:
        raw = (explicit or "").strip()
    else:
        raw = ""
    if not raw:
        raw = (
            os.environ.get("OPENAI_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or "https://api.openai.com/v1"
        ).strip()
    return normalize_openai_compatible_base_url(raw)


def chat_message_content(data: dict[str, Any]) -> str:
    """Extract assistant text from a /chat/completions JSON body."""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("LLM response missing choices")
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        raise ValueError("LLM response missing message")
    content = msg.get("content")
    if content is None or (isinstance(content, str) and not content.strip()):
        raise ValueError(
            "LLM 返回的 assistant 内容为空。若使用 DeepSeek，请将模型设为 deepseek-chat；"
            "deepseek-reasoner 面向推理对话，结构化 JSON 输出请用 chat 模型。"
        )
    return str(content)