from __future__ import annotations

import json
import os
from typing import Any

import httpx

from xjf_pentagi.llm_compat import (
    chat_message_content,
    normalize_openai_compatible_base_url,
    resolve_llm_api_key,
    resolve_llm_base_url,
)
from xjf_pentagi.registry import ToolDef, tool_allowed_for_scope


def _openai_compatible_chat(
    *,
    base_url: str,
    api_key: str,
    model: str,
    system: str,
    user: str,
) -> str:
    base_url = normalize_openai_compatible_base_url(base_url)
    url = base_url.rstrip("/") + "/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
    }
    with httpx.Client(timeout=120.0) as client:
        r = client.post(url, headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    return chat_message_content(data)


def build_llm_plan(
    *,
    goal: str,
    allowed_targets: list[str],
    tools: dict[str, ToolDef],
    scope_profiles: dict[str, bool],
    api_key: str | None = None,
    base_url: str | None = None,
    model: str | None = None,
) -> list[dict[str, Any]]:
    """Call an OpenAI-compatible /chat/completions API; return parsed steps or raise."""
    key = resolve_llm_api_key(api_key)
    if not key:
        raise RuntimeError(
            "LLM API key missing: set OPENAI_API_KEY or DEEPSEEK_API_KEY, or pass api_key"
        )
    url_base = resolve_llm_base_url(base_url)
    mdl = (model or os.environ.get("XJF_LLM_MODEL", "gpt-4o-mini")).strip()

    tool_lines = []
    for tid, td in sorted(tools.items()):
        if not tool_allowed_for_scope(td, scope_profiles):
            continue
        tool_lines.append(f"- {tid}: {td.description} (binary: {td.binary})")
    tools_block = "\n".join(tool_lines) if tool_lines else "(none — enable profiles in scope.yaml)"

    system = (
        "You assist with AUTHORIZED security assessments only. "
        "You must output a single JSON object, no markdown fences, with this shape:\n"
        '{"steps":[{"tool":"<tool_id>","target":"<must be from allowed_targets>",'
        '"args":["..."]}]}\n'
        "Rules: args must NOT repeat the target (the runner appends target). "
        "Only use tool_ids listed. Only use targets from the allowed list exactly as given. "
        "If you cannot comply, return {\"steps\":[]}."
    )
    user = (
        f"Goal: {goal}\n\n"
        f"allowed_targets (JSON array): {json.dumps(allowed_targets, ensure_ascii=False)}\n\n"
        f"Available tools:\n{tools_block}\n"
    )
    raw = _openai_compatible_chat(
        base_url=url_base,
        api_key=key,
        model=mdl,
        system=system,
        user=user,
    )
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    data = json.loads(text)
    steps = data.get("steps")
    if not isinstance(steps, list):
        raise ValueError("LLM JSON missing list 'steps'")
    out: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        out.append(
            {
                "tool": str(step.get("tool", "")),
                "target": str(step.get("target", "")),
                "args": list(step.get("args") or []),
                "_order": i,
            }
        )
    return out
