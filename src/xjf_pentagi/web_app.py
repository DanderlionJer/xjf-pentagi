from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

import yaml

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from xjf_pentagi import __version__
from xjf_pentagi.automation import load_modules, run_full_autonomous
from xjf_pentagi.fsenc import read_text_flexible
from xjf_pentagi.phases import PHASES
from xjf_pentagi.pipelines import list_pipeline_summaries, run_pipeline
from xjf_pentagi.registry import load_tools, tool_allowed_for_scope
from xjf_pentagi.runner import run_tool
from xjf_pentagi.scope import Scope, load_scope_from_env, parse_targets_blob
from xjf_pentagi.llm_compat import resolve_llm_api_key, resolve_llm_base_url
from xjf_pentagi.nl_chat import parse_natural_request, summarize_run_for_user


def _config_dir() -> Path:
    raw = os.environ.get("XJF_CONFIG_DIR", "").strip()
    return Path(raw) if raw else Path("config")


def _output_dir() -> Path:
    raw = os.environ.get("XJF_OUTPUT_DIR", "").strip()
    return Path(raw) if raw else Path("output")


def _static_dir() -> Path:
    return Path(__file__).resolve().parent / "static"


def _scope_yaml_path() -> Path:
    return _config_dir() / "scope.yaml"


def _validate_scope_yaml_text(text: str) -> None:
    try:
        yaml.safe_load(text)
    except yaml.YAMLError as e:
        raise ValueError(f"Invalid YAML: {e}") from e
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".yaml",
        delete=False,
    ) as f:
        f.write(text)
        tmp_path = Path(f.name)
    try:
        Scope.load(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


def _resolve_api_targets(target: str | None, targets: list[str] | None) -> list[str]:
    out: list[str] = []
    if targets:
        for t in targets:
            s = (t or "").strip()
            if s:
                out.append(s)
    if target:
        out.extend(parse_targets_blob(target))
    seen: set[str] = set()
    uniq: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            uniq.append(t)
    if not uniq:
        raise HTTPException(
            status_code=400,
            detail="至少填写一个受测目标（每行一个 URL / 主机 / IP）",
        )
    return uniq


def _verify_ui_token(authorization: str | None = Header(None)) -> None:
    tok = os.environ.get("XJF_UI_TOKEN", "").strip()
    if not tok:
        return
    if (authorization or "").strip() != f"Bearer {tok}":
        raise HTTPException(status_code=401, detail="Invalid or missing UI token (Authorization: Bearer …)")




class ScopeYamlBody(BaseModel):
    yaml: str = Field(..., description="Full scope.yaml content")


class QuickTargetBody(BaseModel):
    url: str = Field(..., description="Target site URL or hostname")


class ExecBody(BaseModel):
    tool: str
    target: str | None = None
    targets: list[str] | None = None
    args: list[str] = Field(default_factory=list)
    dry_run: bool = False


class PipelineBody(BaseModel):
    pipeline: str
    target: str | None = None
    targets: list[str] | None = None
    dry_run: bool = False


class AutoBody(BaseModel):
    target: str | None = None
    targets: list[str] | None = None
    use_llm: bool = True
    dry_run: bool = False
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None


class NaturalBody(BaseModel):
    message: str = Field(..., min_length=1, description="User request in natural language")
    dry_run: bool = True
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None


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


    @api.get("/scope-yaml")
    def api_scope_yaml_get() -> dict[str, str]:
        p = _scope_yaml_path()
        if not p.is_file():
            return {
                "yaml": (
                    "# optional: profiles / explicit whitelist\n"
                    "# Put targets in the multi-line box on the left\n"
                    "profiles: {}\n"
                    "# allowed_hosts: []\n"
                    "# allowed_cidrs: []\n"
                    "# allowed_url_prefixes: []\n"
                )
            }
        return {"yaml": read_text_flexible(p)}

    @api.put("/scope-yaml")
    def api_scope_yaml_put(payload: ScopeYamlBody) -> dict[str, str]:
        text = payload.yaml.replace("\r\n", "\n")
        if text and not text.endswith("\n"):
            text += "\n"
        try:
            _validate_scope_yaml_text(text)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        p = _scope_yaml_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return {"status": "ok"}

    @api.post("/scope/quick-target")
    def api_scope_quick_target(payload: QuickTargetBody) -> dict[str, str]:
        from urllib.parse import urlparse

        raw = (payload.url or "").strip()
        if not raw:
            raise HTTPException(status_code=400, detail="请填写目标网址")
        if "://" not in raw:
            if re.match(r"^[A-Za-z0-9._\-]+$", raw):
                raw = "https://" + raw.strip("/").strip() + "/"
            else:
                raise HTTPException(status_code=400, detail="无效的网站地址")
        parsed = urlparse(raw)
        if not parsed.hostname:
            raise HTTPException(status_code=400, detail="无效的网站地址")
        host = parsed.hostname.lower().rstrip(".")
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc or host
        base = f"{scheme}://{netloc}/"

        path = _scope_yaml_path()
        if path.is_file():
            data = yaml.safe_load(read_text_flexible(path)) or {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}

        hosts = list(data.get("allowed_hosts") or [])
        lowered = [str(h).lower().rstrip(".") for h in hosts]
        if host not in lowered:
            hosts.append(host)
        data["allowed_hosts"] = hosts

        prefs = list(data.get("allowed_url_prefixes") or [])
        if base not in prefs:
            prefs.append(base)
        data["allowed_url_prefixes"] = prefs

        data.setdefault("allowed_cidrs", [])
        data.setdefault("excluded_hosts", [])
        if data.get("max_requests_per_second") in (None, 0):
            data["max_requests_per_second"] = 5
        prof = data.get("profiles")
        if not isinstance(prof, dict) or not prof:
            data["profiles"] = {"web_recon": True, "internal": False}

        out = yaml.dump(
            data, allow_unicode=True, default_flow_style=False, sort_keys=False
        )
        if out and not out.endswith("\n"):
            out += "\n"
        try:
            _validate_scope_yaml_text(out)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(out, encoding="utf-8")
        return {"status": "ok"}

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
                prof_ok = bool(scope.profiles.get(str(req), True))
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

    @api.post("/exec")
    def api_exec(payload: ExecBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        if payload.tool not in defs:
            raise HTTPException(status_code=400, detail="Unknown tool")
        td = defs[payload.tool]
        try:
            tts = _resolve_api_targets(payload.target, payload.targets)
        except HTTPException:
            raise
        try:
            if len(tts) == 1:
                return run_tool(scope, td, tts[0], payload.args, output_dir=out, dry_run=payload.dry_run)
            results = [
                run_tool(scope, td, t, payload.args, output_dir=out, dry_run=payload.dry_run) for t in tts
            ]
            return {"tool": payload.tool, "count": len(results), "results": results}
        except (ValueError, PermissionError, FileNotFoundError) as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.post("/pipeline")
    def api_pipeline(payload: PipelineBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        path = cfg / "pipelines.yaml"
        if not path.is_file():
            raise HTTPException(status_code=500, detail="pipelines.yaml missing")
        try:
            tts = _resolve_api_targets(payload.target, payload.targets)
        except HTTPException:
            raise
        try:
            if len(tts) == 1:
                results = run_pipeline(
                    pipeline_id=payload.pipeline,
                    raw_target=tts[0],
                    scope=scope,
                    tools=defs,
                    pipelines_path=path,
                    output_dir=out,
                    dry_run=payload.dry_run,
                )
                return {"pipeline": payload.pipeline, "results": results}
            by_target: list[dict] = []
            for t in tts:
                by_target.append(
                    {
                        "target": t,
                        "results": run_pipeline(
                            pipeline_id=payload.pipeline,
                            raw_target=t,
                            scope=scope,
                            tools=defs,
                            pipelines_path=path,
                            output_dir=out,
                            dry_run=payload.dry_run,
                        ),
                    }
                )
            return {"pipeline": payload.pipeline, "targets": tts, "by_target": by_target}
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e

    @api.post("/autonomous")
    def api_autonomous(payload: AutoBody) -> dict:
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        ppath = cfg / "pipelines.yaml"
        if not ppath.is_file():
            raise HTTPException(status_code=500, detail="pipelines.yaml missing")
        try:
            tts = _resolve_api_targets(payload.target, payload.targets)
        except HTTPException:
            raise
        try:
            return run_full_autonomous(
                raw_targets=tts,
                scope=scope,
                tools=defs,
                pipelines_path=ppath,
                output_dir=out,
                use_llm=payload.use_llm,
                dry_run=payload.dry_run,
                llm_api_key=payload.llm_api_key,
                llm_base_url=payload.llm_base_url,
                llm_model=payload.llm_model,
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e


    @api.post("/natural")
    def api_natural(payload: NaturalBody) -> dict[str, Any]:
        key = resolve_llm_api_key(payload.llm_api_key)
        if not key:
            raise HTTPException(
                status_code=400,
                detail="自然语言模式需要大模型：请在侧栏「高级选项」填写 LLM API Key，或设置环境变量 OPENAI_API_KEY / DEEPSEEK_API_KEY。",
            )
        base = resolve_llm_base_url(payload.llm_base_url)
        model = (payload.llm_model or os.environ.get("XJF_LLM_MODEL", "gpt-4o-mini")).strip()
        cfg = _config_dir()
        out = _output_dir()
        scope = load_scope_from_env(cfg)
        defs = load_tools(cfg / "tools.yaml")
        ppath = cfg / "pipelines.yaml"
        if not ppath.is_file():
            raise HTTPException(status_code=500, detail="pipelines.yaml missing")
        summaries = list_pipeline_summaries(ppath)
        pipeline_ids = [str(x["id"]) for x in summaries]
        blurb = "\n".join(
            f"- {x['id']}: {x.get('title', '')} — {x.get('description', '')}"
            for x in summaries
        )
        try:
            parsed = parse_natural_request(
                payload.message,
                pipeline_ids=pipeline_ids,
                pipelines_blurb=blurb,
                scope=scope,
                api_key=key,
                base_url=base,
                model=model,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"理解你的说法时出错：{e}") from e
        targets = parsed["targets"]
        if not targets:
            raise HTTPException(
                status_code=400,
                detail="没有从话里识别出要测的目标，请写上域名、URL 或 IP。",
            )
        for t in targets:
            try:
                scope.validate_target(t)
            except ValueError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"目标未通过授权校验：{t}（{e}）",
                ) from e
        pid = str(parsed["pipeline_id"])
        dry = bool(payload.dry_run)
        all_results: list[dict[str, Any]] = []
        for raw_t in targets:
            results = run_pipeline(
                pipeline_id=pid,
                raw_target=raw_t,
                scope=scope,
                tools=defs,
                pipelines_path=ppath,
                output_dir=out,
                dry_run=dry,
            )
            all_results.append({"target": raw_t, "results": results})
        raw_for_summary = all_results[0] if len(all_results) == 1 else all_results
        try:
            reply = summarize_run_for_user(
                payload.message,
                pipeline_id=pid,
                dry_run=dry,
                results=raw_for_summary,
                api_key=key,
                base_url=base,
                model=model,
            )
        except Exception as e:
            reply = f"测试已跑完，但生成中文摘要时出错：{e}\n可在下方 raw 查看结构化结果。"
        return {
            "reply": reply,
            "intent_brief": parsed.get("brief_zh") or "",
            "pipeline_id": pid,
            "targets": targets,
            "dry_run": dry,
            "raw": raw_for_summary,
        }


    app.include_router(api)
    return app


app = create_app()
