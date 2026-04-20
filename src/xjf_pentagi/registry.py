from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ToolDef:
    tool_id: str
    binary: str
    category: str
    profiles: list[str]
    description: str


def load_tools(path: Path) -> dict[str, ToolDef]:
    data: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    raw = data.get("tools") or {}
    out: dict[str, ToolDef] = {}
    for tid, row in raw.items():
        if not isinstance(row, dict):
            continue
        out[tid] = ToolDef(
            tool_id=tid,
            binary=str(row.get("binary", tid)),
            category=str(row.get("category", "misc")),
            profiles=list(row.get("profiles") or []),
            description=str(row.get("description", "")),
        )
    return out


def tool_allowed_for_scope(tool: ToolDef, scope_profiles: dict[str, bool]) -> bool:
    if not tool.profiles:
        return True
    for p in tool.profiles:
        if scope_profiles.get(p):
            return True
    return False
