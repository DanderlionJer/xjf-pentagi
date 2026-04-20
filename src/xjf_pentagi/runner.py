from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from xjf_pentagi.registry import ToolDef, tool_allowed_for_scope
from xjf_pentagi.scope import Scope


def run_tool(
    scope: Scope,
    tool: ToolDef,
    target: str,
    extra_argv: list[str],
    *,
    output_dir: Path,
    dry_run: bool = False,
) -> dict:
    scope.validate_target(target)
    if not tool_allowed_for_scope(tool, scope.profiles):
        raise PermissionError(
            f"Tool '{tool.tool_id}' requires a scope profile in {tool.profiles}; "
            "enable it in scope.yaml under profiles.*"
        )
    binary = shutil.which(tool.binary)
    if not binary:
        raise FileNotFoundError(f"Binary not found in PATH: {tool.binary}")

    argv = [binary, *extra_argv]
    # Many tools expect target as last argument
    full_argv = [*argv, target]

    record: dict = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "tool": tool.tool_id,
        "binary": binary,
        "target": target,
        "argv": full_argv,
        "dry_run": dry_run,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "runs.jsonl"
    if dry_run:
        record["exit_code"] = None
        record["stdout"] = ""
        record["stderr"] = "(dry-run)"
        log_path.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    proc = subprocess.run(
        full_argv,
        capture_output=True,
        text=True,
        timeout=3600,
        check=False,
    )
    record["exit_code"] = proc.returncode
    record["stdout"] = proc.stdout
    record["stderr"] = proc.stderr
    log_path.open("a", encoding="utf-8").write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
