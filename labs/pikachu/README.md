# Pikachu lab (Docker)

Local build uses official `php:7.4-apache` + `mysql:8.0` (works when third-party Hub images are mirror-blocked).

## Start

```bash
cd labs/pikachu
docker compose up -d --build
```

Open **http://127.0.0.1:8765/** and use the on-screen link to **initialize the database** (first run only).

Default DB password in container: `root` / `pikachu` (already written into Pikachu `config.inc.php` by the image).

## Stop

```bash
docker compose down
```

Data is kept in volume `pikachu_mysql_data`. To reset: `docker compose down -v`.

## xjf-pentagi scope example

In `xjf-pentagi/config/scope.yaml` add:

```yaml
allowed_hosts:
  - 127.0.0.1
allowed_url_prefixes:
  - "http://127.0.0.1:8765/"
```

From the host, run tools that need to reach the container via published port `8765`.
If you run **xjf-pentagi inside Docker**, use http://host.docker.internal:8765/ in scope and as URL targets (not 127.0.0.1).
