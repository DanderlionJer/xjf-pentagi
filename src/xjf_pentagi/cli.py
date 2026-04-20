from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import click

from xjf_pentagi import __version__
from xjf_pentagi.phases import PHASES
from xjf_pentagi.planner import build_llm_plan
from xjf_pentagi.registry import load_tools, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import Scope, load_scope_from_env


def _config_dir() -> Path:
    raw = os.environ.get("XJF_CONFIG_DIR", "").strip()
    return Path(raw) if raw else Path("config")


def _output_dir() -> Path:
    raw = os.environ.get("XJF_OUTPUT_DIR", "").strip()
    return Path(raw) if raw else Path("output")


def _tools_path(cfg: Path) -> Path:
    return cfg / "tools.yaml"


@click.group()
@click.version_option(__version__, prog_name="xjf")
def main() -> None:
    """Scoped pentest orchestration (authorized use only)."""


@main.command("doctor")
def doctor() -> None:
    """Check config paths and scope file."""
    cfg = _config_dir()
    scope_path = cfg / "scope.yaml"
    tools_path = _tools_path(cfg)
    click.echo(f"config dir: {cfg.resolve()}")
    click.echo(f"scope.yaml exists: {scope_path.is_file()}")
    click.echo(f"tools.yaml exists: {tools_path.is_file()}")
    if scope_path.is_file():
        s = Scope.load(scope_path)
        click.echo(f"allowed_hosts: {s.allowed_hosts}")
        click.echo(f"profiles: {s.profiles}")


@main.command("phases")
def phases_cmd() -> None:
    """Print built-in methodology phases."""
    for p in PHASES:
        click.echo(f"\n[{p['id']}] {p['title']}")
        for h in p["hints"]:
            click.echo(f"  - {h}")


@main.command("tools")
@click.option("--json-out", "as_json", is_flag=True, help="Print as JSON")
def tools_list(as_json: bool) -> None:
    """List tools from tools.yaml filtered by current scope profiles."""
    cfg = _config_dir()
    scope = load_scope_from_env(cfg)
    defs = load_tools(_tools_path(cfg))
    rows = []
    for tid, td in sorted(defs.items()):
        ok = tool_allowed_for_scope(td, scope.profiles)
        rows.append(
            {
                "id": tid,
                "binary": td.binary,
                "category": td.category,
                "allowed": ok,
                "profiles": td.profiles,
                "description": td.description,
            }
        )
    if as_json:
        click.echo(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    for r in rows:
        flag = "Y" if r["allowed"] else "N"
        click.echo(f"[{flag}] {r['id']}: {r['binary']} — {r['description']}")


@main.command("scope-check")
@click.argument("target")
def scope_check(target: str) -> None:
    """Validate a host, IP, or URL against scope.yaml."""
    cfg = _config_dir()
    scope = load_scope_from_env(cfg)
    try:
        scope.validate_target(target)
    except ValueError as e:
        click.echo(f"NOT ALLOWED: {e}", err=True)
        sys.exit(2)
    click.echo("OK: target is within scope.")


@main.command("exec")
@click.option("--tool", "tool_id", required=True, help="Tool id from tools.yaml")
@click.option("--target", required=True, help="Host, IP, or URL (must match scope)")
@click.option(
    "--dry-run",
    is_flag=True,
    help="Validate only; log intent without running the binary",
)
@click.argument("extra", nargs=-1)
def exec_cmd(tool_id: str, target: str, dry_run: bool, extra: tuple[str, ...]) -> None:
    """Run a registered tool; target is appended as the last argument."""
    cfg = _config_dir()
    out = _output_dir()
    scope = load_scope_from_env(cfg)
    defs = load_tools(_tools_path(cfg))
    if tool_id not in defs:
        raise click.ClickException(f"Unknown tool: {tool_id}")
    td = defs[tool_id]
    try:
        record = run_tool(
            scope,
            td,
            target,
            list(extra),
            output_dir=out,
            dry_run=dry_run,
        )
    except (ValueError, PermissionError, FileNotFoundError) as e:
        raise click.ClickException(str(e)) from e

    click.echo(json.dumps(record, ensure_ascii=False, indent=2))
    if not dry_run and record.get("exit_code") not in (0, None):
        sys.exit(int(record["exit_code"]) if record["exit_code"] is not None else 1)


@main.command("plan-local")
def plan_local() -> None:
    """Print a non-LLM checklist tied to methodology phases."""
    cfg = _config_dir()
    scope = load_scope_from_env(cfg)
    defs = load_tools(_tools_path(cfg))
    allowed = [tid for tid, td in sorted(defs.items()) if tool_allowed_for_scope(td, scope.profiles)]
    payload = {
        "scope_profiles": scope.profiles,
        "allowed_tools": allowed,
        "phases": [{"id": p["id"], "title": p["title"], "hints": p["hints"]} for p in PHASES],
    }
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@main.command("serve")
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind address")
@click.option("--port", default=8080, show_default=True, type=int, help="HTTP port")
def serve_cmd(host: str, port: int) -> None:
    """Start the web UI (FastAPI + static console)."""
    import uvicorn

    from xjf_pentagi.web_app import app

    uvicorn.run(app, host=host, port=port, log_level="info")


@main.command("plan-llm")
@click.option("--goal", required=True, help="High-level authorized task description")
@click.option("--execute", is_flag=True, help="Run each planned step via exec (still scope-checked)")
def plan_llm(goal: str, execute: bool) -> None:
    """Ask an OpenAI-compatible model for a JSON tool plan (requires API key)."""
    cfg = _config_dir()
    out = _output_dir()
    scope = load_scope_from_env(cfg)
    defs = load_tools(_tools_path(cfg))

    targets: list[str] = []
    targets.extend(scope.allowed_hosts)
    for net in scope.allowed_cidrs:
        targets.append(str(net))
    targets.extend(scope.allowed_url_prefixes)

    try:
        steps = build_llm_plan(
            goal=goal,
            allowed_targets=targets,
            tools=defs,
            scope_profiles=scope.profiles,
        )
    except Exception as e:
        raise click.ClickException(f"LLM planning failed: {e}") from e

    click.echo(json.dumps({"steps": steps}, ensure_ascii=False, indent=2))

    if not execute:
        return

    for step in steps:
        tid = step.get("tool", "")
        target = step.get("target", "")
        args = [str(a) for a in (step.get("args") or [])]
        if tid not in defs:
            click.echo(f"skip unknown tool: {tid}", err=True)
            continue
        click.echo(f"\n--- exec {tid} {target} {' '.join(args)}")
        try:
            record = run_tool(scope, defs[tid], target, args, output_dir=out, dry_run=False)
        except Exception as e:
            click.echo(f"FAILED: {e}", err=True)
            continue
        click.echo(record.get("stdout", "")[-4000:])


if __name__ == "__main__":
    main()
