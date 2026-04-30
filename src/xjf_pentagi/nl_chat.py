"""Natural-language intent parsing and human-readable summaries (OpenAI-compatible LLM)."""

from __future__ import annotations

import json
from typing import Any

import httpx

from xjf_pentagi.llm_compat import chat_message_content, normalize_openai_compatible_base_url
from xjf_pentagi.scope import Scope


def _chat(
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


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        lines = t.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        t = "\n".join(lines).strip()
    return t


def parse_natural_request(
    user_message: str,
    *,
    pipeline_ids: list[str],
    pipelines_blurb: str,
    scope: Scope,
    api_key: str,
    base_url: str,
    model: str,
) -> dict[str, Any]:
    """Return dict with keys: targets (list[str]), pipeline_id (str), dry_run (bool), brief_zh (str)."""
    system = (
        "你只协助「已书面授权」的安全测试。用户会用中文描述想测什么。\n"
        "你必须只输出一个 JSON 对象，不要 markdown，不要其它说明。格式如下：\n"
        '{"targets":["目标1"],"pipeline_id":"…","dry_run":true,"brief_zh":"一句话重复用户意图"}\n'
        "规则：\n"
        f"- pipeline_id 必须是下列之一：{json.dumps(pipeline_ids, ensure_ascii=False)}\n"
        "- targets：从用户话里提取域名、URL 或 IP；可多个；不要编造。\n"
        "- 若用户明确说真实执行、不要演练、不要 dry，则 dry_run 为 false，否则 true。\n"
        "- 若用户只要测网页可用性/HTTP，倾向 web_probe；要主机信息/WHOIS/DNS/端口用 recon_host；"
        "两者都要用 recon_full。\n"
        "- 无法判断 pipeline 时用 recon_full。\n"
    )
    allowed_hint: list[str] = []
    allowed_hint.extend(scope.allowed_hosts)
    allowed_hint.extend(scope.allowed_url_prefixes)
    user = (
        f"用户原话：\n{user_message.strip()}\n\n"
        f"可选流程说明：\n{pipelines_blurb}\n\n"
        f"scope.yaml 中已列出的授权提示（可能为空，表示由用户在界面填的目标为准）：\n"
        f"{json.dumps(allowed_hint, ensure_ascii=False)}\n"
    )
    raw = _chat(
        base_url=base_url, api_key=api_key, model=model, system=system, user=user
    )
    data = json.loads(_strip_json_fence(raw))
    if not isinstance(data, dict):
        raise ValueError("LLM 返回不是 JSON 对象")
    targets = data.get("targets")
    if not isinstance(targets, list):
        raise ValueError("JSON 缺少列表 targets")
    targets = [str(x).strip() for x in targets if str(x).strip()]
    pid = str(data.get("pipeline_id") or "").strip()
    if pid not in pipeline_ids:
        raise ValueError(f"无效的 pipeline_id: {pid!r}")
    dry = data.get("dry_run")
    if not isinstance(dry, bool):
        dry = True
    brief = str(data.get("brief_zh") or "").strip()
    return {
        "targets": targets,
        "pipeline_id": pid,
        "dry_run": dry,
        "brief_zh": brief,
    }


def summarize_run_for_user(
    user_message: str,
    *,
    pipeline_id: str,
    dry_run: bool,
    results: Any,
    api_key: str,
    base_url: str,
    model: str,
) -> str:
    """Turn structured pipeline results into plain Chinese for operators."""
    system = (
        "你是安全测试报告助手。根据下面的原始 JSON 结果，用简洁、分条的中文写给操作者看：\n"
        "- 先说这是「演练」还是「真实执行」（依据 dry_run）。\n"
        "- 按步骤说明：哪一步成功、跳过、失败；失败原因用人话写（例如本机未安装某命令）。\n"
        "- 不要重复整段 JSON；不要给攻击建议；不要提未授权测试。\n"
        "直接输出正文，不要标题套话，不要用 markdown 代码块。"
    )
    payload = {
        "user_request": user_message.strip(),
        "pipeline_id": pipeline_id,
        "dry_run": dry_run,
        "results": results,
    }
    user = "原始结果 JSON：\n" + json.dumps(payload, ensure_ascii=False, indent=2)[:120000]
    return _chat(
        base_url=base_url, api_key=api_key, model=model, system=system, user=user
    ).strip()