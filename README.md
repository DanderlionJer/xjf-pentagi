# xjf-pentagi

**xjf-pentagi** is a scope-first orchestration tool for **authorized** security assessments. You declare what is allowed (`config/scope.yaml`), register tools (`config/tools.yaml`), and every run—CLI, web UI, fixed pipelines, or LLM-assisted flows—is checked against that scope before anything executes.

> **Only use this on assets you are explicitly permitted to test.** You are responsible for legal, contractual, and organizational compliance.

---

## What you get

| Area | Description |
|------|-------------|
| **Scope** | `config/scope.yaml` — allowed hosts (with subdomain rules), CIDRs, URL prefixes, and feature profiles (`web_recon`, `internal`, …). |
| **Tools** | `config/tools.yaml` — registry of binaries; they must exist in the environment (Docker image PATH or local install). |
| **CLI** | `xjf` — doctor, list tools, validate targets, run a single tool, optional LLM planning. |
| **Web UI** | `xjf serve` — browser console for modules, **natural language** requests (LLM parses intent, then fixed pipelines), fixed pipelines, and full-chain automation. Static assets live under `src/xjf_pentagi/static/`. |
| **Pipelines** | `config/pipelines.yaml` — ordered steps (`recon_host`, `web_probe`, `recon_full`, …); each step is scope-checked. |
| **Modules** | `config/modules.yaml` — groups tools for the UI. |
| **Output** | Run history appends to `output/runs.jsonl` (when using the default output layout). |

---

## Requirements

- **Python** 3.11+ (see `pyproject.toml`).
- **Dependencies**: Click, PyYAML, httpx, FastAPI, Uvicorn (installed via `pip install -e .`).
- **External tools**: Whatever you list in `tools.yaml` (curl, nmap, etc.). The **web** Docker profile ships a smaller toolset; use **`XJF_PROFILE=full`** for a heavier image (e.g. LDAP/SMB helpers).

---

## Install and run (local)

```bash
pip install -e .
set XJF_CONFIG_DIR=config
xjf doctor
```

Start the web console:

```bash
set XJF_CONFIG_DIR=config
xjf serve --host 127.0.0.1 --port 8080
```

Open [http://127.0.0.1:8080/](http://127.0.0.1:8080/). Interactive API docs: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs).

Optional hardening: set `XJF_UI_TOKEN` and send `Authorization: Bearer <token>` on `/api/*` requests (the UI can store the token).

---

## Docker quick start

```bash
cd xjf-pentagi
copy config\scope.example.yaml config\scope.yaml
# Edit config\scope.yaml for your authorized targets only.

docker compose build
docker compose up -d
```

Default UI: [http://localhost:8080](http://localhost:8080) (override host port with `XJF_UI_PORT`).

One-off CLI inside the container:

```bash
docker compose run --rm orchestrator xjf doctor
docker compose run --rm orchestrator xjf tools
docker compose run --rm orchestrator xjf scope-check example.com
docker compose run --rm orchestrator xjf exec --tool curl --target https://example.com/ -- -fsSL -o /dev/null -w "%{http_code}\n"
```

**Full image** (more OS packages for internal-profile tools):

```bash
set XJF_PROFILE=full
docker compose build --build-arg PROFILE=full
docker compose run --rm orchestrator xjf tools
```

Enable `profiles.internal: true` in `scope.yaml` where appropriate for tools such as `ldapsearch` / `smbclient`.

Compose passes through `XJF_CONFIG_DIR` and `XJF_OUTPUT_DIR` inside the container; config is mounted read-only from `./config`, output from `./output`.

---

## CLI commands (summary)

| Command | Purpose |
|---------|---------|
| `xjf doctor` | Sanity-check config paths and basics. |
| `xjf tools` | List registered tools (JSON with `--json`). |
| `xjf phases` | Show methodology phase metadata if configured. |
| `xjf scope-check <target>` | Validate a host/URL against `scope.yaml`. |
| `xjf exec --tool <id> --target <url-or-host> [--dry-run] -- <args...>` | Run one tool; target is appended; scope + profile enforced. |
| `xjf plan-llm --goal "..."` | Ask an OpenAI-compatible model for a JSON step plan; `--execute` runs each step with the same scope checks. |
| `xjf plan-local` | Local planning helper (no LLM). |
| `xjf serve --host ... --port ...` | Start the FastAPI web app and static UI. |

---

## Web UI tabs

- **测试模块** — Run individual tools from `modules.yaml`.
- **自然语言** — Describe the task in Chinese; requires an LLM. The backend calls **`POST /api/natural`**, parses intent into targets + pipeline, runs scope validation, executes pipelines, then returns a **plain-language summary**. Dry-run follows the global **「仅校验 / 干跑」** checkbox, not the model’s guess.
- **固定流程** — Run pipelines from `pipelines.yaml`.
- **全链路** — Fixed recon pipeline plus optional LLM planning phase (`POST /api/autonomous`), same constraints as `plan-llm`.

---

## LLM integration (OpenAI-compatible)

Any provider that implements **`POST {base}/v1/chat/completions`** with Bearer auth works: OpenAI, **DeepSeek**, OpenRouter, SiliconFlow, self-hosted vLLM, etc.

**Environment variables** (optional; UI “高级选项” can override key/base/model per session):

| Variable | Role |
|----------|------|
| `OPENAI_API_KEY` | Primary API key name (historical; used for all compatible providers). |
| `DEEPSEEK_API_KEY` | Used if `OPENAI_API_KEY` is unset. |
| `OPENAI_BASE_URL` | Default base URL (must end with `/v1` for typical providers), e.g. `https://api.openai.com/v1`. |
| `DEEPSEEK_BASE_URL` | Used if `OPENAI_BASE_URL` is unset. |
| `XJF_LLM_MODEL` | Default model id (e.g. `gpt-4o-mini`, `deepseek-chat`). |

**DeepSeek notes:**

- You may paste `https://api.deepseek.com` as the base URL; the app normalizes it to `https://api.deepseek.com/v1`.
- For **structured JSON** (planning, natural-language intent parsing), prefer **`deepseek-chat`**. The reasoning model is aimed at dialogue, not reliable JSON payloads.

Example:

```bash
docker compose run --rm -e OPENAI_API_KEY=%OPENAI_API_KEY% orchestrator xjf plan-llm --goal "Map HTTPS entrypoint for authorized asset"
```

Add `--execute` to run planned steps (each target is re-validated).

---

## Configuration layout

- `config/scope.yaml` — authorization boundary (required for meaningful runs).
- `config/tools.yaml` — tool ids, binaries, categories, required profiles.
- `config/modules.yaml` — UI groupings of tool ids.
- `config/pipelines.yaml` — multi-step flows (`tool`, `target_mode`: `host` or `url`, `args`).
- `config/phases.yaml` — optional methodology phases for reporting/UI.

Copy `config/scope.example.yaml` to `config/scope.yaml` and edit for your engagement.

---

## Extending the stack

1. Install packages in the `Dockerfile` (`apt-get`) or on the host PATH.
2. Add entries to `config/tools.yaml`.
3. Map tools to `profiles` and enable those profiles in `scope.yaml`.
4. Expose tools in the Web UI via `config/modules.yaml`.
5. Add or adjust pipelines in `config/pipelines.yaml`.

---

## Desktop executable (Windows)

The sibling project **[xjf-pentagi2](https://github.com/DanderlionJer/xjf-pentagi2)** wraps this stack in a single Windows `.exe` (Edge WebView + embedded API). See that repository for build instructions (`build.bat`). Treat the `.exe` as a **frozen snapshot**: changing Python source here does not update the binary until you rebuild there.

---

## License

MIT — for lawful, authorized testing only.
