from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from xjf_pentagi import __version__
from xjf_pentagi.automation import load_modules, run_full_autonomous
from xjf_pentagi.phases import PHASES
from xjf_pentagi.pipelines import list_pipeline_summaries, run_pipeline
from xjf_pentagi.registry import load_tools, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import load_scope_from_env


def _config_dir() -> Path:
    raw = os.environ.get("XJF_CONFIG_DIR", "").strip()
    return Path(raw) if raw else Path("config")


def _output_dir() -> Path:
    raw = os.environ.get("XJF_OUTPUT_DIR", "").strip()
    return Path(raw) if raw else Path("output")


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def _verify_ui_token(authorization: str | None = Header(None)) -> None:
    tok = os.environ.get("XJF_UI_TOKEN", "").strip()
    if not tok:
        return
    if (authorization or "").strip() != f"Bearer {tok}":
        raise HTTPException(status_code=401, detail="Invalid or missing UI token (Authorization: Bearer …)")


def create_app() -> FastAPI:
    app = FastAPI(title="xjf-pentagi", version=__version__)
    static = _static_dir()
    if static.is_dir():
        app.mount("/static", StaticFiles(directory=str(static)), name="static")

    @app.get("/", response_model=None)
    def index():
        index_f = static / "index.html"
        if not index_f.is_file():
            return JSONResponse(
                {"name": "xjf-pentagi", "version": __version__, "docs": "/docs", "health": "/api/health"}
            )
        return FileResponse(index_f)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    api = APIRouter(prefix="/api", dependencies=[Depends(_verify_ui_token)])

    @api.get("/scope")
    def api_scope() -> dict:
        cfg = _config_dir()
        scope = load_scope_from_env(cfg)
        return {
            "allowed_hosts": scope.allowed_hosts,
            "allowed_cidrs": [str(n) for n in scope.allowed_cidrs],
            "allowed_url_prefixes": scope.allowed_url_prefixes,
            "profiles": scope.profiles,
        }

    @api.get("/tools")
    def api_tools() -> list[dict]:
        cfg = _config_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        rows = []
        for tid, td in sorted(defs.items()):
            rows.append(
                {
                    "id": tid,
                    "binary": td.binary,
                    "category": td.category,
                    "allowed": tool_allowed_for_scope(td, scope.profiles),
                    "description": td.description,
                    "profiles": td.profiles,
                }
            )
        return rows

    @api.get("/modules")
    def api_modules() -> list[dict]:
        cfg = _config_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        mod_path = cfg / "modules.yaml"
        if not mod_path.is_file():
            return []
        raw_mods = load_modules(mod_path)
        out: list[dict] = []
        for m in raw_mods:
            req = m.get("requires_profile")
            prof_ok = True
            if req:
                prof_ok = bool(scope.profiles.get(str(req)))
            tool_ids = [str(x) for x in (m.get("tool_ids") or [])]
            tools_payload = []
            for tid in tool_ids:
                if tid not in defs:
                    continue
                td = defs[tid]
                tools_payload.append(
                    {
                        "id": tid,
                        "binary": td.binary,
                        "category": td.category,
                        "allowed": tool_allowed_for_scope(td, scope.profiles),
                        "description": td.description,
                    }
                )
            out.append(
                {
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "description": m.get("description"),
                    "icon": m.get("icon"),
                    "kind": m.get("kind", "tools"),
                    "requires_profile": req,
                    "profile_enabled": prof_ok,
                    "tools": tools_payload,
                }
            )
        return out

    @api.get("/pipelines")
    def api_pipelines() -> list[dict]:
        cfg = _config_dir()
        p = cfg / "pipelines.yaml"
        if not p.is_file():
            return []
        return list_pipeline_summaries(p)

    @api.get("/phases")
    def api_phases() -> list:
        return PHASES

    class ExecBody(BaseModel):
        tool: str
        target: str
        args: list[str] = Field(default_factory=list)
        dry_run: bool = False

    @api.post("/exec")
    def api_exec(body: ExecBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        if body.tool not in defs:
            raise HTTPException(status_code=400, detail="Unknown tool")
        td = defs[body.tool]
        try:
            return run_tool(scope, td, body.target, body.args, output_dir=out, dry_run=body.dry_run)
        except (ValueError, PermissionError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    class PipelineBody(BaseModel):
        pipeline: str
        target: str
        dry_run: bool = False

    @api.post("/pipeline")
    def api_pipeline(body: PipelineBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        path = cfg / "pipelines.yaml"
        if not path.is_file():
            raise HTTPException(status_code=500, detail="pipelines.yaml missing")
        try:
            results = run_pipeline(
                pipeline_id=body.pipeline,
                raw_target=body.target,
                scope=scope,
                tools=defs,
                pipelines_path=path,
                output_dir=out,
                dry_run=body.dry_run,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return {"pipeline": body.pipeline, "results": results}

    class AutoBody(BaseModel):
        target: str
        use_llm: bool = True
        dry_run: bool = False

    @api.post("/autonomous")
    def api_autonomous(body: AutoBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        ppath = cfg / "pipelines.yaml"
        if not ppath.is_file():
            raise HTTPException(status_code=500, detail="pipelines.yaml missing")
        try:
            return run_full_autonomous(
                raw_target=body.target,
                scope=scope,
                tools=defs,
                pipelines_path=ppath,
                output_dir=out,
                use_llm=body.use_llm,
                dry_run=body.dry_run,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    app.include_router(api)
    return app


app = create_app()
