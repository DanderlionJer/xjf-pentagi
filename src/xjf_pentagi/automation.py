from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xjf_pentagi.fsenc import read_text_flexible
from xjf_pentagi.llm_compat import resolve_llm_api_key
from xjf_pentagi.planner import build_llm_plan
from xjf_pentagi.pipelines import run_pipeline
from xjf_pentagi.registry import ToolDef, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import Scope


def run_full_autonomous(
    *,
    raw_targets: list[str],
    scope: Scope,
    tools: dict[str, ToolDef],
    pipelines_path: Path,
    output_dir: Path,
    use_llm: bool = True,
    dry_run: bool = False,
    llm_api_key: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
) -> dict[str, Any]:
    if not raw_targets:
        raise ValueError("no targets")

    report: dict[str, Any] = {
        "targets": raw_targets,
        "phases": [],
    }

    by_target: list[dict[str, Any]] = []
    for rt in raw_targets:
        p1 = run_pipeline(
            pipeline_id="recon_full",
            raw_target=rt,
            scope=scope,
            tools=tools,
            pipelines_path=pipelines_path,
            output_dir=output_dir,
            dry_run=dry_run,
        )
        by_target.append({"target": rt, "results": p1})
    report["phases"].append({"name": "recon_full", "by_target": by_target})

    llm_key = resolve_llm_api_key(llm_api_key)
    if use_llm and llm_key:
        targets = scope.allowed_targets_for_llm(raw_targets)
        goal = (
            "Authorized assessment: after recon, propose at most 6 additional safe steps "
            "using only allowed targets. Focus on validation, not destructive action. "
            f"Primary user targets: {", ".join(raw_targets)}"
        )
        llm_error: str | None = None
        try:
            llm_steps = build_llm_plan(
                goal=goal,
                allowed_targets=targets,
                tools=tools,
                scope_profiles=scope.profiles,
                api_key=llm_api_key,
                base_url=llm_base_url,
                model=llm_model,
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
                "reason": "enable use_llm and set API key in UI or OPENAI_API_KEY / DEEPSEEK_API_KEY env",
            }
        )

    return report


def load_modules(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(read_text_flexible(path)) or {}
    mods = data.get("modules")
    if not isinstance(mods, list):
        return []
    return [m for m in mods if isinstance(m, dict)]

