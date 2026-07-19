"""Thin httpx client over the Tetra Host /api/v1 contract.

A ``transport`` can be injected (e.g. ``httpx.ASGITransport(app=...)``) so the
CLI can be tested in-process against the FastAPI app without a live server.
"""

import json
from collections.abc import Iterator
from typing import Any

import httpx


class TetraError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class TetraClient:
    def __init__(
        self,
        base_url: str,
        token: str = "",
        *,
        transport: httpx.BaseTransport | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base = base_url.rstrip("/")
        self.api = f"{self.base}/api/v1"
        self.token = token
        self._transport = transport
        self._timeout = timeout

    def _client(self) -> httpx.Client:
        return httpx.Client(transport=self._transport, timeout=self._timeout)

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, path: str, *, json_body: Any = None, params: dict | None = None) -> Any:
        with self._client() as client:
            response = client.request(
                method, f"{self.api}{path}", headers=self._headers(), json=json_body, params=params
            )
        if response.status_code == 204:
            return None
        if response.status_code >= 400:
            detail: Any = response.text
            try:
                detail = response.json().get("detail", detail)
            except (ValueError, AttributeError):
                pass
            raise TetraError(str(detail), response.status_code)
        try:
            return response.json()
        except ValueError:
            return response.text

    # ── Auth ──────────────────────────────────────────────────────────────
    def login(self, email: str, password: str, code: str | None = None) -> str:
        body: dict[str, Any] = {"email": email, "password": password}
        if code:
            body["code"] = code
        data = self._request("POST", "/auth/login", json_body=body)
        self.token = data["token"]
        return self.token

    def me(self) -> Any:
        return self._request("GET", "/auth/me")

    # ── Reseller (Cloudflare plans + services) ─────────────────────────────
    def cf_services(self) -> Any:
        return self._request("GET", "/cloudflare/services")

    def cf_zone_plans(self, zone_id: str) -> Any:
        return self._request("GET", f"/cloudflare/zones/{zone_id}/plans")

    def cf_zone_subscription(self, zone_id: str) -> Any:
        return self._request("GET", f"/cloudflare/zones/{zone_id}/subscription")

    def cf_activate_plan(self, zone_id: str, rate_plan_id: str, frequency: str = "monthly") -> Any:
        return self._request(
            "POST", f"/cloudflare/zones/{zone_id}/subscription",
            json_body={"rate_plan_id": rate_plan_id, "frequency": frequency},
        )

    def cf_activate_service(self, zone_id: str, service_key: str) -> Any:
        return self._request(
            "POST", f"/cloudflare/zones/{zone_id}/services/{service_key}/activate"
        )

    # ── Reseller (AI models — OpenRouter runtime keys) ─────────────────────
    def ai_models(self) -> Any:
        return self._request("GET", "/ai/models")

    def ai_keys(self) -> Any:
        return self._request("GET", "/ai/keys")

    def ai_provision(self, label: str, limit: float | None = None, limit_reset: str = "monthly") -> Any:
        body: dict = {"label": label, "limit_reset": limit_reset}
        if limit is not None:
            body["limit"] = limit
        return self._request("POST", "/ai/keys", json_body=body)

    def ai_update(self, key_hash: str, limit: float | None = None, disabled: bool | None = None) -> Any:
        body: dict = {}
        if limit is not None:
            body["limit"] = limit
        if disabled is not None:
            body["disabled"] = disabled
        return self._request("PATCH", f"/ai/keys/{key_hash}", json_body=body)

    def ai_revoke(self, key_hash: str) -> Any:
        return self._request("DELETE", f"/ai/keys/{key_hash}")

    def ai_status(self) -> Any:
        return self._request("GET", "/ai/status")

    def ai_chat(self, model: str, prompt: str) -> Any:
        body = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        return self._request("POST", "/ai/chat", json_body=body)

    def ai_usage(self, days: int = 30) -> Any:
        return self._request("GET", "/ai/usage", params={"days": days})

    def credits_balance(self) -> Any:
        return self._request("GET", "/billing/credits")

    def credits_topup(self, tenant_id: str, amount_usd: float) -> Any:
        return self._request(
            "POST", "/billing/credits", json_body={"tenant_id": tenant_id, "amount_usd": amount_usd}
        )

    # ── Object storage (R2 buckets) ────────────────────────────────────────
    def storage_status(self) -> Any:
        return self._request("GET", "/storage/status")

    def storage_buckets(self) -> Any:
        return self._request("GET", "/storage/buckets")

    def storage_create(self, name: str) -> Any:
        return self._request("POST", "/storage/buckets", json_body={"name": name})

    def storage_delete(self, name: str) -> Any:
        return self._request("DELETE", f"/storage/buckets/{name}")

    # ── Scheduled jobs ─────────────────────────────────────────────────────
    def jobs_list(self) -> Any:
        return self._request("GET", "/jobs")

    def jobs_create(self, name: str, cron: str, url: str, method: str = "GET") -> Any:
        return self._request(
            "POST", "/jobs", json_body={"name": name, "cron": cron, "url": url, "method": method}
        )

    def jobs_delete(self, job_id: str) -> Any:
        return self._request("DELETE", f"/jobs/{job_id}")

    # ── Team / RBAC ────────────────────────────────────────────────────────
    def team(self) -> Any:
        return self._request("GET", "/team")

    def team_invite(self, email: str, role: str = "member") -> Any:
        return self._request("POST", "/team/invites", json_body={"email": email, "role": role})

    def team_revoke(self, invite_id: str) -> Any:
        return self._request("DELETE", f"/team/invites/{invite_id}")

    def team_role(self, member_id: str, role: str) -> Any:
        return self._request("POST", f"/team/members/{member_id}/role", json_body={"role": role})

    def team_remove(self, member_id: str) -> Any:
        return self._request("DELETE", f"/team/members/{member_id}")

    # ── Single sign-on (OIDC) ──────────────────────────────────────────────
    def sso_get(self) -> Any:
        return self._request("GET", "/sso")

    def sso_set(self, body: dict[str, Any]) -> Any:
        return self._request("PUT", "/sso", json_body=body)

    def sso_delete(self) -> Any:
        return self._request("DELETE", "/sso")

    # ── Reseller billing (pricing + ledger) ────────────────────────────────
    def billing_pricing(self) -> Any:
        return self._request("GET", "/billing/pricing")

    def billing_set_price(
        self, offering_key: str, *, provider: str = "", cost_shape: str = "recurring",
        wholesale_cost_cents: int = 0, unit: str = "", rule: str = "markup_percent",
        rule_value: float = 0.0,
    ) -> Any:
        return self._request(
            "PUT", f"/billing/pricing/{offering_key}",
            json_body={
                "provider": provider, "cost_shape": cost_shape,
                "wholesale_cost_cents": wholesale_cost_cents, "unit": unit,
                "rule": rule, "rule_value": rule_value,
            },
        )

    def billing_quote(self, offering_key: str, wholesale_cents: int | None = None) -> Any:
        params = {"wholesale_cents": str(wholesale_cents)} if wholesale_cents is not None else None
        return self._request("GET", f"/billing/quote/{offering_key}", params=params)

    def billing_charges(self) -> Any:
        return self._request("GET", "/billing/charges")

    def audit(self, *, limit: int = 50, offset: int = 0, action: str = "", actor: str = "") -> Any:
        params = {"limit": str(limit), "offset": str(offset)}
        if action:
            params["action"] = action
        if actor:
            params["actor"] = actor
        return self._request("GET", "/audit", params=params)

    def account_update(self, full_name: str, email: str) -> Any:
        return self._request(
            "PATCH", "/account", json_body={"full_name": full_name, "email": email}
        )

    def account_password(self, current_password: str, new_password: str) -> Any:
        return self._request(
            "POST", "/account/password",
            json_body={"current_password": current_password, "new_password": new_password},
        )

    def dashboard(self) -> Any:
        return self._request("GET", "/dashboard")

    # ── Projects / deploys ────────────────────────────────────────────────
    def projects(self) -> list[dict]:
        return self._request("GET", "/projects")

    def deploy(self, project_id: str, force: bool = False) -> Any:
        return self._request("POST", f"/projects/{project_id}/deploy", params={"force": "1"} if force else None)

    def update_project(self, project_id: str, **fields: Any) -> Any:
        body = {k: v for k, v in fields.items() if v is not None}
        return self._request("PATCH", f"/projects/{project_id}", json_body=body)

    def app_storages(self, project_id: str) -> Any:
        return self._request("GET", f"/projects/{project_id}/storages")

    def app_storage_add(self, project_id: str, name: str, mount_path: str, host_path: str = "") -> Any:
        body: dict = {"name": name, "mount_path": mount_path}
        if host_path:
            body["host_path"] = host_path
        return self._request("POST", f"/projects/{project_id}/storages", json_body=body)

    def app_storage_rm(self, project_id: str, storage_uuid: str) -> Any:
        return self._request("DELETE", f"/projects/{project_id}/storages/{storage_uuid}")

    def deployments(self, project_id: str) -> list[dict]:
        return self._request("GET", f"/projects/{project_id}/deployments")

    def project_runtime_logs(self, project_id: str, lines: int = 200) -> Any:
        return self._request("GET", f"/projects/{project_id}/logs", params={"lines": str(lines)})

    def project_analytics(self, project_id: str, period: str = "7d") -> Any:
        return self._request("GET", f"/projects/{project_id}/analytics", params={"period": period})

    def project_errors(self, project_id: str) -> Any:
        return self._request("GET", f"/projects/{project_id}/errors")

    def stream_logs(self, project_id: str, deployment_id: str) -> Iterator[tuple[str, dict]]:
        """Yield (event, data) tuples from the SSE build-log stream until done."""
        url = f"{self.api}/projects/{project_id}/deployments/{deployment_id}/logs/stream"
        with self._client() as client, client.stream("GET", url, headers=self._headers()) as response:
            if response.status_code >= 400:
                raise TetraError(f"log stream failed ({response.status_code})", response.status_code)
            event = "message"
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        data = json.loads(payload)
                    except ValueError:
                        data = {"raw": payload}
                    yield event, data
                    event = "message"

    # ── DNS ───────────────────────────────────────────────────────────────
    def dns(self, zone: str | None = None) -> Any:
        return self._request("GET", "/dns", params={"zone": zone} if zone else None)

    def dns_add(
        self, zone_id: str, record_type: str, name: str, content: str, ttl: int = 1, proxied: bool = False
    ) -> Any:
        return self._request(
            "POST",
            f"/dns/zones/{zone_id}/records",
            json_body={"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied},
        )

    def dns_update(
        self,
        zone_id: str,
        record_id: str,
        record_type: str,
        name: str,
        content: str,
        ttl: int = 1,
        proxied: bool = False,
        priority: int | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "type": record_type,
            "name": name,
            "content": content,
            "ttl": ttl,
            "proxied": proxied,
        }
        if priority is not None:
            body["priority"] = priority
        return self._request("PUT", f"/dns/zones/{zone_id}/records/{record_id}", json_body=body)

    def dns_rm(self, zone_id: str, record_id: str) -> Any:
        return self._request("DELETE", f"/dns/zones/{zone_id}/records/{record_id}")

    # ── Zone tools ────────────────────────────────────────────────────────
    def zone_settings(self, zone_id: str) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/settings")

    def zone_set(self, zone_id: str, setting: str, value: str) -> Any:
        return self._request(
            "PATCH", f"/dns/zones/{zone_id}/settings", json_body={"setting": setting, "value": value}
        )

    def zone_dnssec(self, zone_id: str, status: str) -> Any:
        return self._request("PATCH", f"/dns/zones/{zone_id}/dnssec", json_body={"status": status})

    def zone_purge(self, zone_id: str, everything: bool = True, files: list[str] | None = None) -> Any:
        return self._request(
            "POST", f"/dns/zones/{zone_id}/purge", json_body={"everything": everything, "files": files or []}
        )

    def zone_analytics(self, zone_id: str, days: int = 7) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/analytics", params={"days": days})

    def dns_export(self, zone_id: str) -> Any:
        return self._request("GET", f"/dns/zones/{zone_id}/export")

    def dns_import(self, zone_id: str, bind: str) -> Any:
        return self._request("POST", f"/dns/zones/{zone_id}/import", json_body={"bind": bind})

    # ── Env vars ──────────────────────────────────────────────────────────
    def envs(self, project_id: str) -> list[dict]:
        return self._request("GET", f"/projects/{project_id}/envs")

    def env_set(self, project_id: str, key: str, value: str) -> Any:
        return self._request("POST", f"/projects/{project_id}/envs", json_body={"key": key, "value": value})

    def env_rm(self, project_id: str, env_uuid: str) -> Any:
        return self._request("DELETE", f"/projects/{project_id}/envs/{env_uuid}")

    # ── Apps (Tetra Engine — pre-defined Docker containers) ───────────────
    def apps_catalog(self, search: str | None = None, category: str | None = None) -> Any:
        params: dict[str, str] = {}
        if search:
            params["search"] = search
        if category:
            params["category"] = category
        return self._request("GET", "/apps/catalog", params=params or None)

    def apps(self) -> Any:
        return self._request("GET", "/apps")

    def apps_install(self, slug: str, name: str | None = None, domain: str | None = None) -> Any:
        body: dict[str, str] = {"slug": slug}
        if name:
            body["name"] = name
        if domain:
            body["domain"] = domain
        return self._request("POST", "/apps/install", json_body=body)

    def apps_start(self, project: str) -> Any:
        return self._request("POST", f"/apps/{project}/start")

    def apps_stop(self, project: str) -> Any:
        return self._request("POST", f"/apps/{project}/stop")

    def apps_rm(self, project: str, volumes: bool = False) -> Any:
        return self._request("DELETE", f"/apps/{project}", params={"volumes": "1"} if volumes else None)

    def apps_logs(self, project: str) -> Any:
        return self._request("GET", f"/apps/{project}/logs")

    def apps_compute(self, project: str) -> Any:
        return self._request("GET", f"/apps/{project}/compute")

    # ── Deploys (build & run git repos) ───────────────────────────────────
    def deploy_git(self, git_url: str, name: str, ref: str = "main", port: int = 3000) -> Any:
        return self._request(
            "POST", "/deploys/git",
            json_body={"git_url": git_url, "ref": ref, "name": name, "port": port},
        )

    def native_deploys(self) -> Any:
        return self._request("GET", "/deploys")

    def explain_deployment(self, deployment_id: str) -> Any:
        return self._request("GET", f"/deploys/{deployment_id}/explain")

    def explain_error(self, application_id: str, issue_id: str) -> Any:
        return self._request(
            "GET", f"/projects/{application_id}/errors/{issue_id}/explain"
        )

    def list_tokens(self) -> Any:
        return self._request("GET", "/account/tokens")

    def create_token(
        self, name: str, *, read_only: bool = False, expires_in_days: int | None = None
    ) -> Any:
        body: dict[str, Any] = {"name": name}
        if read_only:
            body["read_only"] = True
        if expires_in_days:
            body["expires_in_days"] = expires_in_days
        return self._request("POST", "/account/tokens", json_body=body)

    def revoke_token(self, token_id: str) -> Any:
        return self._request("DELETE", f"/account/tokens/{token_id}")

    # --- Two-factor auth ---
    def two_factor_status(self) -> Any:
        return self._request("GET", "/account/2fa")

    def two_factor_setup(self) -> Any:
        return self._request("POST", "/account/2fa/setup")

    def two_factor_enable(self, code: str) -> Any:
        return self._request("POST", "/account/2fa/enable", json_body={"code": code})

    def two_factor_disable(self, password: str) -> Any:
        return self._request("POST", "/account/2fa/disable", json_body={"password": password})

    def deploy_status(self, deployment_id: str) -> Any:
        return self._request("GET", f"/deploys/{deployment_id}")

    def rollback_deploy(self, deployment_id: str) -> Any:
        return self._request("POST", f"/deploys/{deployment_id}/rollback")

    def stream_deploy_logs(self, deployment_id: str) -> Iterator[tuple[str, dict]]:
        """Yield (event, data) tuples from a native deploy's SSE build-log stream."""
        url = f"{self.api}/deploys/{deployment_id}/logs/stream"
        with self._client() as client, client.stream("GET", url, headers=self._headers()) as response:
            if response.status_code >= 400:
                raise TetraError(f"log stream failed ({response.status_code})", response.status_code)
            event = "message"
            for line in response.iter_lines():
                if not line:
                    continue
                if line.startswith("event:"):
                    event = line[6:].strip()
                elif line.startswith("data:"):
                    payload = line[5:].strip()
                    try:
                        data = json.loads(payload)
                    except ValueError:
                        data = {"raw": payload}
                    yield event, data
                    event = "message"

    def deploy_env(self, project: str) -> Any:
        return self._request("GET", f"/deploys/{project}/env")

    def deploy_env_set(
        self, project: str, key: str, value: str, is_secret: bool = False, is_build_time: bool = False
    ) -> Any:
        return self._request(
            "POST", f"/deploys/{project}/env",
            json_body={"key": key, "value": value, "is_secret": is_secret, "is_build_time": is_build_time},
        )

    def deploy_env_rm(self, project: str, key: str) -> Any:
        return self._request("DELETE", f"/deploys/{project}/env/{key}")

    def create_deploy_hook(
        self, project: str, git_url: str, ref: str = "main", port: int = 3000,
        previews: bool = True,
    ) -> Any:
        return self._request(
            "POST", "/deploy-hooks",
            json_body={
                "project": project, "git_url": git_url, "ref": ref, "port": port,
                "previews": previews,
            },
        )

    def deploy_hooks(self) -> Any:
        return self._request("GET", "/deploy-hooks")

    def delete_deploy_hook(self, hook_id: str) -> Any:
        return self._request("DELETE", f"/deploy-hooks/{hook_id}")

    # ── Preview environments ──────────────────────────────────────────────
    def previews(self, project: str | None = None) -> Any:
        return self._request("GET", "/previews", params={"project": project} if project else None)

    def delete_preview(self, preview_id: str) -> Any:
        return self._request("DELETE", f"/previews/{preview_id}")

    # ── Own infrastructure (Hetzner, platform-admin) ──────────────────────
    def infra_servers(self) -> Any:
        return self._request("GET", "/infra/servers")

    def infra_provision(
        self, name: str, server_type: str = "", image: str = "", location: str = "",
        role: str = "docker", mail_hostname: str = "",
    ) -> Any:
        return self._request(
            "POST", "/infra/servers",
            json_body={
                "name": name, "server_type": server_type, "image": image,
                "location": location, "role": role, "mail_hostname": mail_hostname,
            },
        )

    def infra_destroy(self, server_id: int) -> Any:
        return self._request("DELETE", f"/infra/servers/{server_id}")

    # ── Custom domains ────────────────────────────────────────────────────
    def domains(self, project: str | None = None) -> Any:
        return self._request("GET", "/domains", params={"project": project} if project else None)

    def domain_add(self, project: str, hostname: str) -> Any:
        return self._request(
            "POST", "/domains", json_body={"project": project, "hostname": hostname}
        )

    def domain_verify(self, domain_id: str) -> Any:
        return self._request("POST", f"/domains/{domain_id}/verify")

    def domain_rm(self, domain_id: str) -> Any:
        return self._request("DELETE", f"/domains/{domain_id}")

    # ── Plans ─────────────────────────────────────────────────────────────
    def plans(self, include_archived: bool = False) -> list[dict]:
        return self._request("GET", "/plans", params={"include_archived": str(include_archived).lower()})

    def plan_create(self, **fields: Any) -> Any:
        return self._request("POST", "/plans", json_body=fields)

    def plan_update(self, plan_id: int | str, **fields: Any) -> Any:
        return self._request("PATCH", f"/plans/{plan_id}", json_body=fields)

    def plan_archive(self, plan_id: int | str) -> Any:
        return self._request("POST", f"/plans/{plan_id}/archive")

    # ── Tenants ───────────────────────────────────────────────────────────
    def tenants(self) -> list[dict]:
        return self._request("GET", "/tenants")

    def tenant_action(self, slug: str, action: str) -> Any:
        return self._request("POST", f"/tenants/{slug}/{action}")

    # ── Platform admin ────────────────────────────────────────────────────
    def admin_overview(self) -> Any:
        return self._request("GET", "/admin/overview")

    # ── Databases ─────────────────────────────────────────────────────────
    def databases(self) -> list[dict]:
        return self._request("GET", "/databases")

    def provision_database(
        self,
        db_type: str,
        name: str,
        server_uuid: str,
        project_uuid: str,
        environment_name: str,
    ) -> Any:
        return self._request(
            "POST",
            "/databases",
            json_body={
                "type": db_type,
                "name": name,
                "server_uuid": server_uuid,
                "project_uuid": project_uuid,
                "environment_name": environment_name,
            },
        )

    def database_backups(self, uuid: str) -> list[dict]:
        return self._request("GET", f"/databases/{uuid}/backups")

    def create_database_backup(self, uuid: str, **config: Any) -> Any:
        return self._request("POST", f"/databases/{uuid}/backups", json_body=config or None)

    # ── Usage ─────────────────────────────────────────────────────────────
    def usage(self) -> Any:
        return self._request("GET", "/usage")

    # ── Mail (Phase 2) ────────────────────────────────────────────────────
    def mail(self, refresh: bool = False) -> Any:
        return self._request("GET", "/mail", params={"refresh": "1"} if refresh else None)

    def create_mail_domain(
        self, domain: str, *, description: str = "", quota_mb: int = 10240
    ) -> Any:
        return self._request(
            "POST",
            "/mail/domains",
            json_body={"domain": domain, "description": description, "quota_mb": quota_mb},
        )

    def delete_mail_domain(self, domain: str) -> Any:
        return self._request("DELETE", f"/mail/domains/{domain}")

    def create_mailbox(
        self,
        local_part: str,
        domain: str,
        *,
        password: str,
        name: str = "",
        quota_mb: int = 3072,
    ) -> Any:
        return self._request(
            "POST",
            "/mail/mailboxes",
            json_body={
                "local_part": local_part,
                "domain": domain,
                "password": password,
                "name": name,
                "quota_mb": quota_mb,
            },
        )

    def edit_mailbox(
        self,
        username: str,
        *,
        quota_mb: int | None = None,
        name: str | None = None,
        active: bool | None = None,
        password: str | None = None,
    ) -> Any:
        body: dict[str, Any] = {}
        if quota_mb is not None:
            body["quota_mb"] = quota_mb
        if name is not None:
            body["name"] = name
        if active is not None:
            body["active"] = active
        if password is not None:
            body["password"] = password
        return self._request("PATCH", f"/mail/mailboxes/{username}", json_body=body)

    def delete_mailbox(self, username: str) -> Any:
        return self._request("DELETE", f"/mail/mailboxes/{username}")

    def list_app_passwords(self, username: str) -> Any:
        return self._request("GET", f"/mail/mailboxes/{username}/app-passwords")

    def create_app_password(self, username: str, app_name: str = "Tetra app password") -> Any:
        return self._request(
            "POST",
            f"/mail/mailboxes/{username}/app-passwords",
            json_body={"app_name": app_name},
        )

    def delete_app_password(self, username: str, app_passwd_id: int | str) -> Any:
        return self._request(
            "DELETE", f"/mail/mailboxes/{username}/app-passwords/{app_passwd_id}"
        )

    def mail_quarantine(self) -> Any:
        return self._request("GET", "/mail/quarantine")

    def quarantine_action(self, ids: list[int], action: str = "release") -> Any:
        return self._request(
            "POST", "/mail/quarantine/actions", json_body={"ids": ids, "action": action}
        )

    def quarantine_delete(self, ids: list[int]) -> Any:
        return self._request("POST", "/mail/quarantine/delete", json_body={"ids": ids})

    def mail_aliases(self, refresh: bool = False) -> Any:
        return self._request("GET", "/mail/aliases", params={"refresh": "1"} if refresh else None)

    def create_mail_alias(self, address: str, goto: str) -> Any:
        return self._request("POST", "/mail/aliases", json_body={"address": address, "goto": goto})

    def delete_mail_alias(self, alias_id: int | str) -> Any:
        return self._request("DELETE", f"/mail/aliases/{alias_id}")

    def mail_dkim(self, domain: str) -> Any:
        return self._request("GET", f"/mail/domains/{domain}/dkim")

    def list_mail_relayhosts(self) -> Any:
        return self._request("GET", "/mail/relayhosts")

    def create_mail_relayhost(self, hostname: str, username: str, password: str) -> Any:
        return self._request(
            "POST",
            "/mail/relayhosts",
            json_body={"hostname": hostname, "username": username, "password": password},
        )
