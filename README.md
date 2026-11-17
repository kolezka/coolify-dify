# Dify on Coolify

Deploy [Dify](https://github.com/langgenius/dify) — the open-source LLM app development platform — on [Coolify](https://coolify.io) as a single Docker Compose resource.

This repo is a **curated, Coolify-tuned** version of Dify's official Docker Compose stack. Point Coolify at it, assign a domain, click deploy. Coolify generates all secrets and handles TLS; there is nothing to configure by hand to get a working instance.

- **Dify version:** `1.19.0` (pinned)
- **Vector store:** Weaviate
- **Everything runs in one stack** on a single domain.

> Not affiliated with LangGenius/Dify or Coolify. This is deployment glue around their official images.

---

## What gets deployed

A single `docker-compose.yaml` running the core Dify stack:

| Service | Image | Purpose |
| --- | --- | --- |
| `nginx` | `nginx` | Single ingress — Coolify routes your domain here |
| `web` | `langgenius/dify-web` | Next.js frontend |
| `api` | `langgenius/dify-api` | Console + service API |
| `api_websocket` | `langgenius/dify-api` | Real-time collaboration (socket.io) |
| `worker` | `langgenius/dify-api` | Celery worker (indexing, workflows, mail) |
| `worker_beat` | `langgenius/dify-api` | Scheduled tasks |
| `plugin_daemon` | `langgenius/dify-plugin-daemon` | Installs & runs plugins |
| `sandbox` | `langgenius/dify-sandbox` | Isolated code execution |
| `ssrf_proxy` | `ubuntu/squid` | SSRF-protected outbound proxy |
| `agent_backend` | `langgenius/dify-agent-backend` | Agent v2 runtime |
| `local_sandbox` | `langgenius/dify-agent-local-sandbox` | Shell workspaces for agents |
| `agent_ssrf_proxy` | `ubuntu/squid` | Outbound proxy for `local_sandbox` only |
| `db_postgres` | `postgres:15-alpine` | Metadata database |
| `redis` | `redis:6-alpine` | Cache + Celery broker |
| `weaviate` | `semitechnologies/weaviate` | Vector store |

All persistent data lives in named Docker volumes managed by Coolify. Config files (nginx templates, squid config, sandbox config, the postgres init script) are embedded in `docker-compose.yaml` as inline `configs:`.

### Editing a config file

Coolify does not copy repository files for a Git-based Compose deploy: a bind mount such as `./nginx/nginx.conf.template` arrives as an empty directory. So the files under `nginx/`, `ssrf_proxy/`, `volumes/sandbox/` and `postgres/` are the source, and `docker-compose.yaml` carries a generated copy. After editing one of them, run:

```bash
python3 scripts/embed-configs.py          # rewrite the embedded block
python3 scripts/embed-configs.py --check  # exit 1 if the block is stale
```

The script writes every `$` as `$$`, so Compose leaves the `${...}` placeholders alone for `envsubst` inside the containers.

---

## Requirements

- A running **Coolify** instance (v4+).
- A server/destination with at least **4 GB RAM** and ~10 GB free disk (8 GB RAM recommended). The plugin daemon and vector store are memory-hungry.
- A domain or subdomain you can point at the server (Coolify can also generate a temporary `sslip.io` domain for testing).

---

## Deploy on Coolify

1. **New Resource → Docker Compose.**
   - Choose your Project and Server.
   - Source: **Public Repository** (or your fork) — URL: `https://github.com/kolezka/coolify-dify`
   - Branch: `main`
   - Coolify auto-detects `docker-compose.yaml`. Leave the compose path as the default (`/docker-compose.yaml`).

2. **Set the domain.**
   - Open the **`nginx`** service and set its **Domain** to the URL you want, e.g. `https://dify.example.com`.
   - Coolify wires this to the `SERVICE_FQDN_NGINX_80` variable and terminates HTTPS at its own proxy. Leave Dify's internal HTTPS off (it already is).
   - No ports need to be exposed manually.

3. **Deploy.** Coolify auto-generates all `SERVICE_PASSWORD_*` secrets on first deploy. The first boot pulls several images and runs database migrations, so give it a few minutes. Watch the `api` logs until you see it serving on `:5001`.

4. **First-run setup.** Open your domain. Dify shows an admin-account setup screen — create your admin user. Then go to **Settings → Model Provider** and add an API key (OpenAI, Anthropic, etc.) to start building.

That's it.

---

## How secrets & the domain work

This template relies on [Coolify magic variables](https://coolify.io/docs/knowledge-base/environment-variables) so you never handle secrets manually:

| Variable | Used for |
| --- | --- |
| `SERVICE_FQDN_NGINX_80` | Assigns your domain to nginx and routes Coolify's proxy to port 80 |
| `SERVICE_PASSWORD_POSTGRES` | PostgreSQL password (shared by api, worker, plugin daemon) |
| `SERVICE_PASSWORD_REDIS` | Redis password (also embedded in the Celery broker URL) |
| `SERVICE_PASSWORD_WEAVIATE` | Weaviate API key |
| `SERVICE_PASSWORD_64_SECRETKEY` | Dify `SECRET_KEY` (session signing) |
| `SERVICE_PASSWORD_64_PLUGINDAEMON` | Plugin daemon server key |
| `SERVICE_PASSWORD_64_INNERAPI` | Inner API key between Dify and the plugin daemon |
| `SERVICE_PASSWORD_64_AGENTAPI` | Token between the API and the agent backend |
| `SERVICE_PASSWORD_64_SHELLCTL` | Token between the agent backend and `local_sandbox` |
| `SERVICE_PASSWORD_64_AGENTSECRET` | Seed for `DIFY_AGENT_SERVER_SECRET_KEY` |

`DIFY_AGENT_SERVER_SECRET_KEY` must be unpadded base64url of exactly 32 bytes, which no magic variable produces. `agent_backend` derives it at startup as the SHA-256 of the seed. Set `DIFY_AGENT_SERVER_SECRET_KEY` yourself to override (generate with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`).

Coolify generates each value once and reuses it across services and redeploys. Every other setting has a sensible default in `docker-compose.yaml` and can be overridden from the app's **Environment Variables** tab in Coolify.

---

## Upgrading Dify

Image tags are pinned in `docker-compose.yaml`. To upgrade:

1. Bump the `langgenius/dify-*` image tags (and, when needed, `dify-sandbox` / `dify-plugin-daemon`) to the target Dify release. Check the [Dify releases](https://github.com/langgenius/dify/releases) and their upgrade notes.
2. Commit and push.
3. Redeploy in Coolify.

Database migrations run automatically on `api` startup (`MIGRATION_ENABLED=true`). Your data persists in the named volumes across redeploys. Take a backup / snapshot before major version jumps.

### From 1.15.0 to 1.19.0

- Weaviate goes from `1.27.0` to `1.39.13`. Back up `dify_weaviate_data` first and check Weaviate's migration notes for the versions in between; an existing install with data may need intermediate tags. A fresh install is not affected.
- New services `agent_backend`, `local_sandbox` and `agent_ssrf_proxy` and three new secrets. Coolify generates the secrets on the next deploy.
- Upstream nginx now sends `X-Forwarded-For: $remote_addr`. Behind Coolify that is the proxy's address, so Dify logs and rate limits see Traefik, not the client.
- The plugin daemon (0.6.x) runs as uid 1001. `init_permissions` now also hands `dify_plugin_daemon` to that user, so installing plugins no longer fails with `mkdir /app/storage/assets: permission denied`. Each volume has its own flag file, so existing installs get the fix on the next deploy.

---

## Persistence & backups

Data is stored in named volumes: `dify_app_storage` (uploaded files), `dify_db_data` (Postgres), `dify_redis_data`, `dify_weaviate_data` (vectors), `dify_plugin_daemon`, `dify_sandbox_dependencies`, and the agent workspaces `dify_agent_local_sandbox_home` and `dify_agent_local_sandbox_workspace`. Use Coolify's scheduled backups for `db_postgres`, and back up the storage and weaviate volumes for a complete restore.

---

## Local testing (without Coolify)

Run the Compose regression checks without starting containers:

```bash
python3 -I -m unittest discover -s tests -v
```

The frontend sets `HOSTNAME=0.0.0.0` so Next.js accepts traffic on every Docker network interface. Keep this override when deploying behind Coolify's proxy.

```bash
cp .env.example .env
# edit .env: set your own random secrets in the "Secrets" block
docker compose up -d
```

By default nginx is only exposed inside the Docker network (Coolify's proxy connects to it). To reach it locally, publish a port with an override file:

```yaml
# docker-compose.override.yaml
services:
  nginx:
    ports:
      - "8080:80"
```

Then open <http://localhost:8080>. For plain-HTTP local use, also set `NEXT_PUBLIC_SOCKET_URL=ws://localhost:8080` in `.env`.

---

## Notes & caveats

- **Sandbox key:** the code-execution sandbox uses Dify's default internal key and is only reachable on an internal Docker network (never exposed). This matches upstream defaults.
- **Single vector store:** Weaviate is included. Switching to another store (pgvector, Qdrant, Milvus, …) means adding that container and setting `VECTOR_STORE` — see the [Dify docs](https://docs.dify.ai/).
- **Email, OAuth, S3 storage, observability**, etc. are not preconfigured — add the relevant environment variables in Coolify when you need them (see Dify's `.env.example` reference).
- This template targets a single-node deploy. For HA/scale, consult Dify's production guidance.

---

## License

The deployment configuration in this repository is released under the [MIT License](LICENSE). Dify and the container images it ships are covered by their own licenses — see the [Dify repository](https://github.com/langgenius/dify).
