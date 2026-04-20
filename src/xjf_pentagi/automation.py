from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from xjf_pentagi.planner import build_llm_plan
from xjf_pentagi.pipelines import run_pipeline
from xjf_pentagi.registry import ToolDef, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import Scope


def run_full_autonomous(
    *,
    raw_target: str,
    scope: Scope,
    tools: dict[str, ToolDef],
    pipelines_path: Path,
    output_dir: Path,
    use_llm: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Full-chain automation: fixed recon pipeline first, then optional LLM-planned steps.
    All steps remain scope-checked.
    """
    report: dict[str, Any] = {
        "target_input": raw_target,
        "phases": [],
    }

    p1 = run_pipeline(
        pipeline_id="recon_full",
        raw_target=raw_target,
        scope=scope,
        tools=tools,
        pipelines_path=pipelines_path,
        output_dir=output_dir,
        dry_run=dry_run,
    )
    report["phases"].append({"name": "recon_full", "results": p1})

    if use_llm and os.environ.get("OPENAI_API_KEY", "").strip():
        targets: list[str] = []
        targets.extend(scope.allowed_hosts)
        for net in scope.allowed_cidrs:
            targets.append(str(net))
        targets.extend(scope.allowed_url_prefixes)
        if raw_target.strip() and raw_target.strip() not in targets:
            targets.append(raw_target.strip())

        goal = (
            "Authorized assessment: after recon, propose at most 6 additional safe steps "
            "using only allowed targets. Focus on validation, not destructive action. "
            f"Primary user target: {raw_target.strip()}"
        )
        llm_error: str | None = None
        try:
            llm_steps = build_llm_plan(
                goal=goal,
                allowed_targets=targets,
                tools=tools,
                scope_profiles=scope.profiles,
            )
        except Exception as e:
            llm_error = str(e)
            llm_steps = []

        exec_results: list[dict[str, Any]] = []
        for step in llm_steps:
            tid = step.get("tool", "")
            target = step.get("target", "")
            args = [str(a) for a in (step.get("args") or [])]
            if tid not in tools:
                exec_results.append({"tool": tid, "skipped": True, "error": "unknown_tool"})
                continue
            td = tools[tid]
            if not tool_allowed_for_scope(td, scope.profiles):
                exec_results.append({"tool": tid, "skipped": True, "error": "profile_not_enabled"})
                continue
            try:
                record = run_tool(scope, td, target, args, output_dir=output_dir, dry_run=dry_run)
                exec_results.append(record)
            except Exception as e:
                exec_results.append({"tool": tid, "error": str(e), "skipped": True})

        report["phases"].append(
            {
                "name": "llm_plan",
                "planned_steps": llm_steps,
                "results": exec_results,
                "error": llm_error,
            }
        )
    else:
        report["phases"].append(
            {
                "name": "llm_plan",
                "skipped": True,
                "reason": "set OPENAI_API_KEY and use_llm=true to enable LLM phase",
            }
        )

    return report


def load_modules(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    mods = data.get("modules")
    if not isinstance(mods, list):
        return []
    return [m for m in mods if isinstance(m, dict)]
