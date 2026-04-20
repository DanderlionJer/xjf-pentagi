# xjf-pentagi

Scoped orchestration CLI for **authorized** security assessments: declarative tools, hard **scope** checks before every run, methodology phases, and optional **OpenAI-compatible** LLM planning.

> Use only on systems you are permitted to test. You are responsible for legal and contractual compliance.

## Features

- `config/scope.yaml` — allowed hosts (with subdomain matching), CIDRs, URL prefixes, feature profiles (`web_recon`, `internal`).
- `config/tools.yaml` — tool registry; binaries must exist in the runtime (Docker image or local PATH).
- `xjf exec` — validates target, checks tool vs profile, runs tool with args and appends target as the last argument.
- `xjf plan-llm` — model proposes JSON steps; with `--execute`, each step still passes scope validation.
- Logs append to `output/runs.jsonl`.

## Quick start (Docker)

```bash
cd xjf-pentagi
copy config\scope.example.yaml config\scope.yaml
# Edit config\scope.yaml with your authorized targets

docker compose build
docker compose run --rm orchestrator xjf doctor
docker compose run --rm orchestrator xjf tools
docker compose run --rm orchestrator xjf scope-check example.com
docker compose run --rm orchestrator xjf exec --tool curl --target https://example.com/ -- -fsSL -o /dev/null -w "%{http_code}\n"
```

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

## License

MIT — use only for lawful, authorized testing.
