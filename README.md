# xjf-pentagi

Scoped orchestration CLI for **authorized** security assessments: declarative tools, hard **scope** checks before every run, methodology phases, and optional **OpenAI-compatible** LLM planning.

> Use only on systems you are permitted to test. You are responsible for legal and contractual compliance.

## Features

- `config/scope.yaml` — allowed hosts (with subdomain matching), CIDRs, URL prefixes, feature profiles (`web_recon`, `internal`).
- `config/tools.yaml` — tool registry; binaries must exist in the runtime (Docker image or local PATH).
- `xjf exec` — validates target, checks tool vs profile, runs tool with args and appends target as the last argument.
- `xjf plan-llm` — model proposes JSON steps; with `--execute`, each step still passes scope validation.
- **Web UI** — `xjf serve`: click-to-run modules, fixed pipelines, and optional full-chain automation (recon pipeline + LLM phase). Static console under `src/xjf_pentagi/static/`.
- `config/modules.yaml` — groups tools for the UI (e.g. recon, internal, methodology phases).
- `config/pipelines.yaml` — ordered multi-step chains (`recon_host`, `web_probe`, `recon_full`, …), each step scope-checked.
- Logs append to `output/runs.jsonl`.

## Desktop app (single EXE)

The sibling project **[xjf-pentagi2](https://github.com/DanderlionJer/xjf-pentagi2)** packages this stack into a Windows `.exe` (Edge window + embedded API). Build once with Python, then distribute only the executable. See that repo’s README for `.\build.bat` in PowerShell vs `build.bat` in cmd.

## Web console

Local (after `pip install -e .` and `config/scope.yaml` present):

```bash
set XJF_CONFIG_DIR=config
xjf serve --host 127.0.0.1 --port 8080
```

Open `http://127.0.0.1:8080/`. API docs: `http://127.0.0.1:8080/docs`.

Optional: set `XJF_UI_TOKEN` and send `Authorization: Bearer <token>` on `/api/*` requests (the page has a field for this).

**Full-chain automation** (UI tab “全链路” or `POST /api/autonomous`): runs pipeline `recon_full` first; if `OPENAI_API_KEY` is set and LLM is enabled, runs an LLM-planned phase (same constraints as `plan-llm`).

## Quick start (Docker)

```bash
cd xjf-pentagi
copy config\scope.example.yaml config\scope.yaml
# Edit config\scope.yaml with your authorized targets

docker compose build
# Web UI (default service command): http://localhost:8080
docker compose up -d
# One-off CLI examples:
docker compose run --rm orchestrator xjf doctor
docker compose run --rm orchestrator xjf tools
docker compose run --rm orchestrator xjf scope-check example.com
docker compose run --rm orchestrator xjf exec --tool curl --target https://example.com/ -- -fsSL -o /dev/null -w "%{http_code}\n"
```

Change the host port with `XJF_UI_PORT` (maps host → container `8080`).

### Full image (LDAP/SMB helpers)

```bash
set XJF_PROFILE=full
docker compose build --build-arg PROFILE=full
docker compose run --rm orchestrator xjf tools
```

Enable `profiles.internal: true` in `scope.yaml` for `ldapsearch` / `smbclient`.

## LLM planning

Set `OPENAI_API_KEY` (and optionally `OPENAI_BASE_URL`, `XJF_LLM_MODEL`). Then:

```bash
docker compose run --rm -e OPENAI_API_KEY=%OPENAI_API_KEY% orchestrator xjf plan-llm --goal "Map HTTPS entrypoint for example asset" 
```

Add `--execute` to run planned steps (each target is re-validated).

## Local Python (without Docker)

Requires the same CLI tools installed on your host OS; on Windows, prefer Docker.

```bash
pip install -e .
set XJF_CONFIG_DIR=config
xjf doctor
```

## Extending tools

1. Install packages in `Dockerfile` (`apt-get`) or use a custom image.
2. Add entries to `config/tools.yaml`.
3. Map tools to `profiles` and enable those profiles in `scope.yaml`.
4. To show tools in the Web UI, add their ids under a block in `config/modules.yaml`.
5. To add a click-to-run multi-step flow, define a pipeline in `config/pipelines.yaml` (`steps` with `tool`, `target_mode`: `host` or `url`, and `args`).

## License

MIT — use only for lawful, authorized testing.
