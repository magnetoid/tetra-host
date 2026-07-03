# Combined Provider API Reference

**Date:** 2026-06-30
**Sources fetched this session:**
- `https://raw.githubusercontent.com/coollabsio/coolify/main/openapi.json` — authoritative OpenAPI 3.x spec (96 paths, API version 0.1)
- `https://coolify.io/docs/api-reference/api/` — auth/overview docs
- `https://coolify.io/docs` — general docs index

---

## Coolify API (v4)

**Base URL:** `https://<your-instance>/api/v1`
**Auth:** `Authorization: Bearer {token_id}|{token_secret}`
**Rate limit:** 200 requests/minute
**Total documented paths:** 96

### Verified Gotchas

- **No rollback API.** Rollback is web-UI only (image-based redeploy). No API to deploy a specific commit SHA (see Coolify bug #1976). Do not build API-backed rollback.
- **No execute-command endpoint in the OpenAPI spec.** The repo calls `POST /api/v1/applications/{uuid}/execute` with `{"command": ...}` but this path **does not appear in the official openapi.json**. Treat as undocumented/unofficial — may break on Coolify upgrades.
- **Deploy uses GET (not POST).** `GET /deploy` with query params. A POST body variant is also accepted per docs.
- **Start/stop/restart use GET (not POST).** `GET /applications/{uuid}/start`, etc.
- **Build logs are a polled string.** `GET /applications/{uuid}/logs` returns a growing `deployment_log` string. No native streaming. Diff by line count to stream incrementally.
- **Notifications/webhooks not in API.** No `/notifications`, `/webhooks`, `/slack`, `/discord`, or `/telegram` endpoints exist in the public API. These are UI-only settings.
- **No shared env vars API.** Shared/team-level env vars are UI-only; the API only manages per-resource envs.
- **No Docker cleanup endpoint.** Cleanup is a `docker_cleanup` query param on delete operations, not a standalone endpoint.
- **Hetzner endpoints** (`/hetzner/*`) are cloud-provisioning specific and require a Hetzner cloud token via `/cloud-tokens`.

---

### Applications

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/applications` | List all applications | `tag` (query, optional filter) |
| POST | `/applications/public` | Create from public git repo | body: `project_uuid*`, `server_uuid*`, `environment_name*`, `environment_uuid*`, `git_repository*`, `git_branch*`, `build_pack*`, `ports_exposes`, `destination_uuid`, `name`, `description`, `domains`, `instant_deploy` |
| POST | `/applications/private-github-app` | Create via GitHub App auth | body: `project_uuid*`, `server_uuid*`, `environment_name*`, `environment_uuid*`, `github_app_uuid*`, `git_repository*`, `git_branch*`, `build_pack*`, ... |
| POST | `/applications/private-deploy-key` | Create via SSH deploy key | body: `project_uuid*`, `server_uuid*`, `environment_name*`, `environment_uuid*`, `private_key_uuid*`, `git_repository*`, `git_branch*`, `build_pack*`, ... |
| POST | `/applications/dockerfile` | Create from Dockerfile (no git) | body: `project_uuid*`, `server_uuid*`, `environment_name*`, `environment_uuid*`, `dockerfile*`, `build_pack`, `ports_exposes`, `destination_uuid` |
| POST | `/applications/dockerimage` | Create from Docker image (no git) | body: `project_uuid*`, `server_uuid*`, `environment_name*`, `environment_uuid*`, `docker_registry_image_name*`, `docker_registry_image_tag`, `ports_exposes`, `destination_uuid` |
| GET | `/applications/{uuid}` | Get application by UUID | `uuid` (path) |
| PATCH | `/applications/{uuid}` | Update application | `uuid` (path); body: most app fields |
| DELETE | `/applications/{uuid}` | Delete application | `uuid` (path); query: `delete_configurations`, `delete_volumes`, `docker_cleanup`, `delete_connected_networks` |
| GET | `/applications/{uuid}/start` | Start application | `uuid` (path); query: `force`, `instant_deploy` |
| GET | `/applications/{uuid}/stop` | Stop application | `uuid` (path); query: `docker_cleanup` |
| GET | `/applications/{uuid}/restart` | Restart application | `uuid` (path) |
| GET | `/applications/{uuid}/logs` | Get application container logs | `uuid` (path); query: `lines` |
| GET | `/applications/{uuid}/envs` | List env vars | `uuid` (path) |
| POST | `/applications/{uuid}/envs` | Create env var | body: `key`, `value`, `is_preview`, `is_literal`, `is_multiline`, `is_shown_once` |
| PATCH | `/applications/{uuid}/envs` | Update env var | body: `key*`, `value*`, `is_preview`, `is_literal`, `is_multiline`, `is_shown_once` |
| PATCH | `/applications/{uuid}/envs/bulk` | Bulk update env vars | body: `data*` (array) |
| DELETE | `/applications/{uuid}/envs/{env_uuid}` | Delete env var | `uuid`, `env_uuid` (path) |
| DELETE | `/applications/{uuid}/previews/{pull_request_id}` | Delete PR preview deployment | `uuid`, `pull_request_id` (path) |
| GET | `/applications/{uuid}/storages` | List persistent storage volumes | `uuid` (path) |
| POST | `/applications/{uuid}/storages` | Create storage volume | body: `type*`, `mount_path*`, `name`, `host_path`, `content`, `is_directory`, `fs_path` |
| PATCH | `/applications/{uuid}/storages` | Update storage volume | body: `uuid`, `id`, `type*`, `mount_path`, `host_path`, etc. |
| DELETE | `/applications/{uuid}/storages/{storage_uuid}` | Delete storage volume | `uuid`, `storage_uuid` (path) |
| GET | `/applications/{uuid}/scheduled-tasks` | List scheduled tasks (cron jobs) | `uuid` (path) |
| POST | `/applications/{uuid}/scheduled-tasks` | Create scheduled task | body: `name*`, `command*`, `frequency*`, `container`, `timeout`, `enabled` |
| PATCH | `/applications/{uuid}/scheduled-tasks/{task_uuid}` | Update scheduled task | body: `name`, `command`, `frequency`, `container`, `timeout`, `enabled` |
| DELETE | `/applications/{uuid}/scheduled-tasks/{task_uuid}` | Delete scheduled task | `uuid`, `task_uuid` (path) |
| GET | `/applications/{uuid}/scheduled-tasks/{task_uuid}/executions` | List task execution history | `uuid`, `task_uuid` (path) |

**NOT in spec (used by repo):**
- `POST /applications/{uuid}/execute` — execute shell command in container. Undocumented in openapi.json; used in `app/services/coolify.py:533`. Verify against your Coolify version before relying on it.

---

### Services (One-Click / Compose Services)

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/services` | List all services | — |
| POST | `/services` | Create service | body: `type`, `name`, `description`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `server_uuid*`, `destination_uuid`, `instant_deploy` |
| GET | `/services/{uuid}` | Get service | `uuid` (path) |
| PATCH | `/services/{uuid}` | Update service | body: `name`, `description`, `project_uuid`, `environment_name`, etc. |
| DELETE | `/services/{uuid}` | Delete service | `uuid` (path); query: `delete_configurations`, `delete_volumes`, `docker_cleanup`, `delete_connected_networks` |
| GET | `/services/{uuid}/start` | Start service | `uuid` (path) |
| GET | `/services/{uuid}/stop` | Stop service | `uuid` (path); query: `docker_cleanup` |
| GET | `/services/{uuid}/restart` | Restart service | `uuid` (path); query: `latest` |
| GET | `/services/{uuid}/envs` | List service env vars | `uuid` (path) |
| POST | `/services/{uuid}/envs` | Create env var | body: `key`, `value`, `is_preview`, `is_literal`, `is_multiline`, `is_shown_once` |
| PATCH | `/services/{uuid}/envs` | Update env var | body: `key*`, `value*`, ... |
| PATCH | `/services/{uuid}/envs/bulk` | Bulk update env vars | body: `data*` |
| DELETE | `/services/{uuid}/envs/{env_uuid}` | Delete env var | `uuid`, `env_uuid` (path) |
| GET | `/services/{uuid}/storages` | List service storage volumes | `uuid` (path) |
| POST | `/services/{uuid}/storages` | Create storage volume | body: `type*`, `resource_uuid*`, `mount_path*`, ... |
| PATCH | `/services/{uuid}/storages` | Update storage volume | body: `uuid`, `type*`, `mount_path`, ... |
| DELETE | `/services/{uuid}/storages/{storage_uuid}` | Delete storage volume | `uuid`, `storage_uuid` (path) |
| GET | `/services/{uuid}/scheduled-tasks` | List scheduled tasks | `uuid` (path) |
| POST | `/services/{uuid}/scheduled-tasks` | Create scheduled task | body: `name*`, `command*`, `frequency*`, `container`, `timeout`, `enabled` |
| PATCH | `/services/{uuid}/scheduled-tasks/{task_uuid}` | Update scheduled task | body: `name`, `command`, `frequency`, ... |
| DELETE | `/services/{uuid}/scheduled-tasks/{task_uuid}` | Delete scheduled task | `uuid`, `task_uuid` (path) |
| GET | `/services/{uuid}/scheduled-tasks/{task_uuid}/executions` | List task executions | `uuid`, `task_uuid` (path) |

---

### Databases

Supported types: PostgreSQL, MySQL, MariaDB, MongoDB, Redis, KeyDB, DragonFly, ClickHouse

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/databases` | List all databases | — |
| POST | `/databases/postgresql` | Create PostgreSQL | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `destination_uuid`, `postgres_user`, `postgres_password`, `postgres_db`, ... |
| POST | `/databases/mysql` | Create MySQL | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `destination_uuid`, `mysql_root_password`, `mysql_user`, `mysql_password`, ... |
| POST | `/databases/mariadb` | Create MariaDB | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `destination_uuid`, `mariadb_conf`, `mariadb_root_password`, ... |
| POST | `/databases/mongodb` | Create MongoDB | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `destination_uuid`, `mongo_initdb_root_username`, ... |
| POST | `/databases/redis` | Create Redis | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `destination_uuid`, `redis_password`, `redis_conf`, ... |
| POST | `/databases/keydb` | Create KeyDB | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `keydb_password`, `keydb_conf`, ... |
| POST | `/databases/dragonfly` | Create DragonFly | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `dragonfly_password`, ... |
| POST | `/databases/clickhouse` | Create ClickHouse | body: `server_uuid*`, `project_uuid*`, `environment_name*`, `environment_uuid*`, `clickhouse_admin_user`, `clickhouse_admin_password`, ... |
| GET | `/databases/{uuid}` | Get database | `uuid` (path) |
| PATCH | `/databases/{uuid}` | Update database | body: `name`, `description`, `image`, `is_public`, `public_port`, `limits_memory`, `limits_cpu`, ... |
| DELETE | `/databases/{uuid}` | Delete database | `uuid` (path); query: `delete_configurations`, `delete_volumes`, `docker_cleanup`, `delete_connected_networks` |
| GET | `/databases/{uuid}/start` | Start database | `uuid` (path) |
| GET | `/databases/{uuid}/stop` | Stop database | `uuid` (path); query: `docker_cleanup` |
| GET | `/databases/{uuid}/restart` | Restart database | `uuid` (path) |
| GET | `/databases/{uuid}/envs` | List env vars | `uuid` (path) |
| POST | `/databases/{uuid}/envs` | Create env var | body: `key`, `value`, `is_literal`, `is_multiline`, `is_shown_once` |
| PATCH | `/databases/{uuid}/envs` | Update env var | body: `key*`, `value*`, ... |
| PATCH | `/databases/{uuid}/envs/bulk` | Bulk update env vars | body: `data*` |
| DELETE | `/databases/{uuid}/envs/{env_uuid}` | Delete env var | `uuid`, `env_uuid` (path) |
| GET | `/databases/{uuid}/storages` | List storage volumes | `uuid` (path) |
| POST | `/databases/{uuid}/storages` | Create storage volume | body: `type*`, `mount_path*`, ... |
| PATCH | `/databases/{uuid}/storages` | Update storage volume | — |
| DELETE | `/databases/{uuid}/storages/{storage_uuid}` | Delete storage volume | `uuid`, `storage_uuid` (path) |
| GET | `/databases/{uuid}/backups` | List backup configurations | `uuid` (path) |
| POST | `/databases/{uuid}/backups` | Create backup configuration | body: `frequency*`, `enabled`, `save_s3`, `s3_storage_uuid`, `databases_to_backup`, `dump_all`, `backup_now`, `database_backup_retention_amount_locally`, ... |
| PATCH | `/databases/{uuid}/backups/{scheduled_backup_uuid}` | Update backup configuration | body: `save_s3`, `s3_storage_uuid`, `backup_now`, `enabled`, `databases_to_backup`, `dump_all`, `frequency`, ... |
| DELETE | `/databases/{uuid}/backups/{scheduled_backup_uuid}` | Delete backup configuration | `uuid`, `scheduled_backup_uuid` (path); query: `delete_s3` |
| GET | `/databases/{uuid}/backups/{scheduled_backup_uuid}/executions` | List backup execution history | `uuid`, `scheduled_backup_uuid` (path) |
| DELETE | `/databases/{uuid}/backups/{scheduled_backup_uuid}/executions/{execution_uuid}` | Delete backup execution record | path params + query: `delete_s3` |

---

### Deployments

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/deploy` | Trigger deploy by UUID or tag | query: `uuid` (comma-separated UUIDs), `tag` (comma-separated tags), `force` (bool, no cache), `pr`/`pull_request_id` (PR ID), `docker_tag` (for docker image PR previews) |
| GET | `/deployments` | List currently running deployments | — |
| GET | `/deployments/applications/{uuid}` | List deployments for an application | `uuid` (path); query: `skip`, `take` |
| GET | `/deployments/{uuid}` | Get deployment details (incl. log) | `uuid` (path) |
| POST | `/deployments/{uuid}/cancel` | Cancel a running deployment | `uuid` (path) |

**Notes:**
- No webhook endpoint for deployment events.
- No "deploy specific commit SHA" — only latest commit on the configured branch.
- Deployment logs accessed via `GET /deployments/{uuid}` response field `deployment_log` (polled string, not streamed).

---

### Servers

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/servers` | List all servers | — |
| POST | `/servers` | Create/add server (SSH) | body: `name`, `description`, `ip`, `port`, `user`, `private_key_uuid`, `is_build_server`, `instant_validate` |
| POST | `/servers/hetzner` | Provision Hetzner cloud server | body: `cloud_provider_token_uuid`, `location*`, `server_type*`, `image*`, `name`, `private_key_uuid*`, `enable_ipv4` |
| GET | `/servers/{uuid}` | Get server | `uuid` (path) |
| PATCH | `/servers/{uuid}` | Update server settings | body: `name`, `description`, `ip`, `port`, `user`, `private_key_uuid`, `is_build_server`, `instant_validate` |
| DELETE | `/servers/{uuid}` | Remove server | `uuid` (path) |
| GET | `/servers/{uuid}/validate` | Validate server SSH connectivity | `uuid` (path) |
| GET | `/servers/{uuid}/resources` | List resources on server | `uuid` (path) |
| GET | `/servers/{uuid}/domains` | List domains on server | `uuid` (path) |

---

### Projects and Environments

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/projects` | List all projects | — |
| POST | `/projects` | Create project | body: `name`, `description` |
| GET | `/projects/{uuid}` | Get project | `uuid` (path) |
| PATCH | `/projects/{uuid}` | Update project | body: `name`, `description` |
| DELETE | `/projects/{uuid}` | Delete project | `uuid` (path) |
| GET | `/projects/{uuid}/environments` | List environments in project | `uuid` (path) |
| POST | `/projects/{uuid}/environments` | Create environment | body: `name` |
| GET | `/projects/{uuid}/{environment_name_or_uuid}` | Get environment details | `uuid`, `environment_name_or_uuid` (path) |
| DELETE | `/projects/{uuid}/environments/{environment_name_or_uuid}` | Delete environment | `uuid`, `environment_name_or_uuid` (path) |

---

### Teams

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/teams` | List all teams (root token) | — |
| GET | `/teams/current` | Get authenticated token's team | — |
| GET | `/teams/current/members` | List members of current team | — |
| GET | `/teams/{id}` | Get team by ID | `id` (path) |
| GET | `/teams/{id}/members` | List team members | `id` (path) |

---

### Resources (Cross-Type)

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/resources` | List all resources (apps + dbs + services) across all projects | — |

---

### GitHub Apps / Source Integrations

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/github-apps` | List GitHub Apps | — |
| POST | `/github-apps` | Create GitHub App integration | body: `name*`, `organization`, `api_url*`, `html_url*`, `custom_user`, `custom_port`, `app_id*`, `installation_id*`, ... |
| PATCH | `/github-apps/{github_app_id}` | Update GitHub App | body: `name`, `organization`, `api_url`, `html_url`, etc. |
| DELETE | `/github-apps/{github_app_id}` | Delete GitHub App integration | `github_app_id` (path) |
| GET | `/github-apps/{github_app_id}/repositories` | List repositories accessible via App | `github_app_id` (path) |
| GET | `/github-apps/{github_app_id}/repositories/{owner}/{repo}/branches` | List branches for a repo | `github_app_id`, `owner`, `repo` (path) |

---

### Private Keys (Deploy Keys / SSH Keys)

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/security/keys` | List private keys | — |
| POST | `/security/keys` | Create private key | body: `name`, `description`, `private_key*` |
| PATCH | `/security/keys` | Update private key | body: `name`, `description`, `private_key*` |
| GET | `/security/keys/{uuid}` | Get private key | `uuid` (path) |
| DELETE | `/security/keys/{uuid}` | Delete private key | `uuid` (path) |

---

### Cloud Provider Tokens (Hetzner etc.)

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/cloud-tokens` | List cloud provider tokens | — |
| POST | `/cloud-tokens` | Create cloud provider token | body: `provider*`, `token*`, `name*` |
| GET | `/cloud-tokens/{uuid}` | Get cloud provider token | `uuid` (path) |
| PATCH | `/cloud-tokens/{uuid}` | Update cloud provider token | body: `name` |
| DELETE | `/cloud-tokens/{uuid}` | Delete cloud provider token | `uuid` (path) |
| POST | `/cloud-tokens/{uuid}/validate` | Validate cloud provider token | `uuid` (path) |

---

### Hetzner Cloud Provisioning

| Method | Path | Summary | Key Params |
|--------|------|---------|------------|
| GET | `/hetzner/images` | List available Hetzner images | query: `cloud_provider_token_uuid` or `cloud_provider_token_id` |
| GET | `/hetzner/locations` | List Hetzner datacenter locations | query: `cloud_provider_token_uuid` or `cloud_provider_token_id` |
| GET | `/hetzner/server-types` | List Hetzner server types/sizes | query: `cloud_provider_token_uuid` or `cloud_provider_token_id` |
| GET | `/hetzner/ssh-keys` | List SSH keys in Hetzner account | query: `cloud_provider_token_uuid` or `cloud_provider_token_id` |

---

### API Management / MCP

| Method | Path | Summary | Notes |
|--------|------|---------|-------|
| GET | `/enable` | Enable API access | Requires root token |
| GET | `/disable` | Disable API access | Requires root token |
| POST | `/mcp/enable` | Enable MCP server | — |
| POST | `/mcp/disable` | Disable MCP server | — |

---

### Miscellaneous

| Method | Path | Summary |
|--------|------|---------|
| GET | `/health` | Health check — returns `{"status": "ok"}` |
| GET | `/version` | Get Coolify version |

---

### Capability Gap Analysis (Repo vs. API)

#### What the repo implements correctly (matched to spec)

| Repo Method | API Endpoint | Status |
|-------------|-------------|--------|
| `list_applications` | `GET /applications` | OK |
| `get_application` / `get_application_raw` | `GET /applications/{uuid}` | OK |
| `update_application` | `PATCH /applications/{uuid}` | OK |
| `delete_application` | `DELETE /applications/{uuid}` | OK |
| `deploy_application` | `GET /deploy?uuid=...&force=...` | OK |
| `start_application` | `GET /applications/{uuid}/start` | OK |
| `stop_application` | `GET /applications/{uuid}/stop` | OK |
| `restart_application` | `GET /applications/{uuid}/restart` | OK |
| `get_application_logs` | `GET /applications/{uuid}/logs` | OK |
| `get_application_envs` | `GET /applications/{uuid}/envs` | OK |
| `create_env` | `POST /applications/{uuid}/envs` | OK |
| `update_env` | `PATCH /applications/{uuid}/envs` | OK |
| `delete_env` | `DELETE /applications/{uuid}/envs/{env_uuid}` | OK |
| `list_scheduled_tasks` | `GET /applications/{uuid}/scheduled-tasks` | OK |
| `create_scheduled_task` | `POST /applications/{uuid}/scheduled-tasks` | OK |
| `update_scheduled_task` | `PATCH /applications/{uuid}/scheduled-tasks/{task_uuid}` | OK |
| `delete_scheduled_task` | `DELETE /applications/{uuid}/scheduled-tasks/{task_uuid}` | OK |
| `list_scheduled_task_executions` | `GET /applications/{uuid}/scheduled-tasks/{task_uuid}/executions` | OK |
| `list_storages` | `GET /applications/{uuid}/storages` | OK |
| `create_storage` | `POST /applications/{uuid}/storages` | OK |
| `update_storage` | `PATCH /applications/{uuid}/storages` | OK |
| `delete_storage` | `DELETE /applications/{uuid}/storages/{storage_uuid}` | OK |
| `cancel_deployment` | `POST /deployments/{uuid}/cancel` | OK |
| `get_deployment` | `GET /deployments/{uuid}` | OK |
| `list_deployments_for_application` | `GET /deployments/applications/{uuid}` | OK |
| `list_databases` | `GET /databases` | OK |
| `get_database` | `GET /databases/{uuid}` | OK |
| `start_database` | `GET /databases/{uuid}/start` | OK |
| `stop_database` | `GET /databases/{uuid}/stop` | OK |
| `restart_database` | `GET /databases/{uuid}/restart` | OK |
| `list_services` | `GET /services` | OK |
| `start_service` | `GET /services/{uuid}/start` | OK |
| `stop_service` | `GET /services/{uuid}/stop` | OK |
| `restart_service` | `GET /services/{uuid}/restart` | OK |
| `list_servers` | `GET /servers` | OK |
| `get_server_resources` | `GET /servers/{uuid}/resources` | OK |
| `get_server_domains` | `GET /servers/{uuid}/domains` | OK |
| `validate_server` | `GET /servers/{uuid}/validate` | OK |
| `list_projects` | `GET /projects` | OK |

#### Discrepancies / Risks

| Issue | Detail |
|-------|--------|
| `execute_command` uses undocumented endpoint | `POST /applications/{uuid}/execute` is not in the official OpenAPI spec. The repo calls it at `app/services/coolify.py:533`. It may work but is not guaranteed stable. |
| No notifications via API | No `/notifications`, `/slack`, `/discord`, `/telegram` endpoints exist. Notification settings are UI-only. |
| No rollback API | Confirmed: no rollback endpoint. Do not expose rollback UI backed by API. |
| No commit-SHA deploy | `GET /deploy` only triggers a build from the current branch HEAD, not a specific SHA. |
| Bulk env update exists but may be unused | `PATCH /applications/{uuid}/envs/bulk` with `data*` array exists; verify if the repo uses it. |
| Database env vars not implemented in repo | The API has full CRUD for database env vars (`/databases/{uuid}/envs/*`) but no matching repo methods were found. |
| Service env vars via API exist | The API has `GET/POST/PATCH/DELETE /services/{uuid}/envs` but repo only implements start/stop/restart for services. |
| Database backups API not used by repo | Full backup CRUD exists (`/databases/{uuid}/backups/*`) but no repo methods wrap it. |
| GitHub Apps API unused | Full GitHub App CRUD + repo/branch listing available but no methods in `coolify.py`. |
| Private Keys API unused | `GET/POST/PATCH/DELETE /security/keys` available but no methods in `coolify.py`. |
| Cloud Tokens / Hetzner unused | Full CRUD + Hetzner provisioning API available; not implemented. |
| Services scheduled tasks unused | `GET/POST/PATCH/DELETE /services/{uuid}/scheduled-tasks` available but not in repo. |
| Services storage volumes unused | `GET/POST/PATCH/DELETE /services/{uuid}/storages` available but not in repo. |
| `list_deployments` (global, running) unused | `GET /deployments` lists currently running deployments across all apps; not exposed in repo. |
| PR preview deletion unused | `DELETE /applications/{uuid}/previews/{pull_request_id}` available; not in repo. |
| Docker image application type | `POST /applications/dockerimage` (deploy from registry image without git) available; not in repo. |

## Cloudflare for SaaS — Custom Hostnames (verified 2026-07-02)

Sources: developers.cloudflare.com/cloudflare-for-platforms/cloudflare-for-saas/start/getting-started/,
/api/resources/custom_hostnames/, /rules/origin-rules/

| Method + path | Purpose | Key params / response |
|---|---|---|
| `POST /zones/{zone_id}/custom_hostnames` | Register a customer hostname | body `{hostname, ssl:{method:"http"|"txt"|"email", type:"dv", certificate_authority?}}` → `result.id`, `status`, `ssl.status`, `ssl.validation_records` |
| `GET /zones/{zone_id}/custom_hostnames/{id}` | Poll activation | `status`: active/pending/blocked/…; `ssl.status`: initializing/pending_validation/active/… |
| `DELETE /zones/{zone_id}/custom_hostnames/{id}` | Remove hostname | — |
| `PUT /zones/{zone_id}/custom_hostnames/fallback_origin` | Set SaaS fallback origin | body `{origin}`; origin must be a **proxied** DNS record on the zone |

Gotchas (verified):
- `ssl.method="http"`: CF auto-answers cert validation once the customer's CNAME routes
  through the zone — zero extra customer DNS beyond the CNAME. `txt` requires the customer
  to publish CF's TXT too.
- **Origin Rules destination-port override is available on ALL plans (incl. Free)**;
  Host-header/SNI/DNS-record overrides are Enterprise-only. Whether origin rules apply to
  SaaS custom-hostname traffic is NOT stated in docs — verify empirically with one test
  hostname before relying on the high-port origin pattern.
- Token scope for custom hostnames: Zone > **SSL and Certificates > Edit** (prod token
  must be re-minted; current scopes lack it).
- Envelope as usual: `{success, result, errors}` — read `result`.

---

## Mailcow API — write operations (verified 2026-07-03)

**Source:** `https://raw.githubusercontent.com/mailcow/mailcow-dockerized/master/data/web/api/openapi.yaml` (authoritative spec shipped inside mailcow-dockerized).
**Auth:** `X-API-Key: <key>` header. **Base:** `https://<mailcow-host>`.

**Response envelope for add/edit/delete:** JSON **array** of
`{type: "success"|"danger"|"error", msg: [...], log: [...]}` (the spec sometimes
declares a bare object — real instances return an array; handle both). A 200 with
`type: danger|error` is a FAILED operation — must be surfaced as an error.

| Operation | Method + path | Body (key fields) |
|---|---|---|
| Create domain | `POST /api/v1/add/domain` | `{domain, description?, active, quota, maxquota, defquota, mailboxes, aliases, restart_sogo, rl_frame?, rl_value?}` (quotas in MiB) |
| Update domain | `POST /api/v1/edit/domain` | `{items: [domain,...], attr: {…, relayhost: <id>}}` — partial attrs OK; `relayhost` assigns a sender-dependent transport |
| Delete domain | `POST /api/v1/delete/domain` | JSON array: `["domain.tld", ...]` |
| Create mailbox | `POST /api/v1/add/mailbox` | `{local_part, domain, name?, password, password2, quota, active, force_pw_update?, tls_enforce_in?, tls_enforce_out?}` |
| Delete mailbox | `POST /api/v1/delete/mailbox` | JSON array: `["user@domain.tld", ...]` |
| Create alias | `POST /api/v1/add/alias` | `{address, goto, active}` — `address` `@domain.tld` = catchall; `goto` comma-separated; only one of goto/goto_ham/goto_null/goto_spam |
| Delete alias | `POST /api/v1/delete/alias` | JSON array of alias **ids** as strings: `["6"]` |
| List aliases | `GET /api/v1/get/alias/all` | (the `{id}` routes accept `all` — same convention our `get/domain/all` read already uses) |
| Get DKIM | `GET /api/v1/get/dkim/{domain}` | → `{dkim_selector, dkim_txt, length, pubkey, privkey:""}` — `dkim_txt` is the TXT record CONTENT; record NAME is `{dkim_selector}._domainkey.{domain}` |
| Generate DKIM | `POST /api/v1/add/dkim` | `{domains, dkim_selector (default "dkim"), key_size (1024/2048/3072/4096)}` |
| Delete DKIM | `POST /api/v1/delete/dkim` | JSON array: `["domain.tld"]` |
| Create relayhost | `POST /api/v1/add/relayhost` | `{hostname: "smtp.esp.tld:587", username, password}` — "Sender-Dependent Transports" |
| List relayhosts | `GET /api/v1/get/relayhost/all` | → entries carry `id` used by `edit/domain attr.relayhost` |
| Delete relayhost | `POST /api/v1/delete/relayhost` | JSON array of ids |

### Gotchas

- **HTTP 200 ≠ success** — always inspect the envelope `type`.
- Numeric fields are commonly sent/returned as **strings** ("1", "3072") — normalize.
- Mailbox creation requires `password` AND `password2` (confirmation).
- ESP relay pattern: `add/relayhost` once (platform credential), then per-domain
  `edit/domain {attr: {relayhost: <id>}}` — outbound for that domain routes via the ESP.
- DKIM: generate at domain creation; publish `dkim_txt` at
  `{selector}._domainkey.{domain}` TXT. mailcow does NOT publish DNS itself.
