from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from xjf_pentagi.fsenc import read_text_flexible
from xjf_pentagi.registry import ToolDef, load_tools, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import Scope
from xjf_pentagi.targets import resolve_step_target


def load_pipelines(path: Path) -> dict[str, dict[str, Any]]:
    data = yaml.safe_load(read_text_flexible(path)) or {}
    raw = data.get("pipelines") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for pid, row in raw.items():
        if isinstance(row, dict) and isinstance(row.get("steps"), list):
            out[str(pid)] = row
    return out


def list_pipeline_summaries(path: Path) -> list[dict[str, Any]]:
    pipelines = load_pipelines(path)
    rows = []
    for pid, row in sorted(pipelines.items()):
        rows.append(
            {
                "id": pid,
                "title": row.get("title", pid),
                "description": row.get("description", ""),
                "step_count": len(row.get("steps") or []),
            }
        )
    return rows


def run_pipeline(
    *,
    pipeline_id: str,
    raw_target: str,
    scope: Scope,
    tools: dict[str, ToolDef],
    pipelines_path: Path,
    output_dir: Path,
    dry_run: bool = False,
) -> list[dict[str, Any]]:
    all_p = load_pipelines(pipelines_path)
    if pipeline_id not in all_p:
        raise ValueError(f"Unknown pipeline: {pipeline_id}")
    steps = all_p[pipeline_id].get("steps") or []
    results: list[dict[str, Any]] = []
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            continue
        tid = str(step.get("tool", ""))
        mode = str(step.get("target_mode", "host"))
        args = [str(a) for a in (step.get("args") or [])]
        if tid not in tools:
            results.append(
                {
                    "step": i,
                    "tool": tid,
                    "error": "unknown_tool",
                    "skipped": True,
                }
            )
            continue
        td = tools[tid]
        eff = resolve_step_target(raw_target, mode)
        rec: dict[str, Any] = {"step": i, "tool": tid, "resolved_target": eff}
        try:
            scope.validate_target(eff)
        except ValueError as e:
            rec["error"] = str(e)
            rec["skipped"] = True
            results.append(rec)
            continue
        if not tool_allowed_for_scope(td, scope.profiles):
            rec["error"] = "profile_not_enabled"
            rec["skipped"] = True
            results.append(rec)
            continue
        try:
            record = run_tool(scope, td, eff, args, output_dir=output_dir, dry_run=dry_run)
            rec.update(record)
        except (ValueError, PermissionError, FileNotFoundError) as e:
            rec["error"] = str(e)
            rec["skipped"] = True
        results.append(rec)
    return results
