"""Cloudflare R2 client — resell S3-compatible object storage buckets to tenants.

Buckets are created under the platform Cloudflare account; per-bucket S3 credentials are
minted via the Cloudflare Tokens API (Access Key ID = the token id; Secret Access Key =
SHA-256 of the token value, returned ONCE). Zero egress fees, no capacity planning. All calls
go through the shared retrying ``request_json`` helper.
"""

import hashlib
from typing import Any

import httpx

from app.cache import TTLCache
from app.config import get_settings
from app.services.http import ProviderAPIError, request_json

CLOUDFLARE_API = "https://api.cloudflare.com/client/v4"


class R2Client:
    def __init__(
        self,
        *,
        api_token: str,
        account_id: str,
        permission_group_id: str = "",
        jurisdiction: str = "default",
        http_client: httpx.AsyncClient,
        cache: TTLCache,
    ) -> None:
        self.api_token = api_token
        self.account_id = account_id
        self.permission_group_id = permission_group_id
        self.jurisdiction = jurisdiction or "default"
        self.http_client = http_client
        self.cache = cache

    @classmethod
    def from_settings(cls, *, http_client: httpx.AsyncClient, cache: TTLCache) -> "R2Client":
        s = get_settings()
        return cls(
            api_token=s.cloudflare_api_token,
            account_id=s.cloudflare_account_id,
            permission_group_id=s.cloudflare_r2_permission_group_id,
            jurisdiction=s.cloudflare_r2_jurisdiction,
            http_client=http_client,
            cache=cache,
        )

    def is_configured(self) -> bool:
        return bool(self.api_token and self.account_id)

    def can_issue_credentials(self) -> bool:
        return self.is_configured() and bool(self.permission_group_id)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

    @property
    def s3_endpoint(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def _base(self) -> str:
        return f"{CLOUDFLARE_API}/accounts/{self.account_id}"

    async def list_buckets(self) -> list[dict[str, Any]]:
        payload = await request_json(
            self.http_client, service="Cloudflare R2", method="GET",
            url=f"{self._base()}/r2/buckets", headers=self.headers(),
        )
        result = payload.get("result") if isinstance(payload, dict) else None
        buckets = result.get("buckets") if isinstance(result, dict) else result
        return buckets if isinstance(buckets, list) else []

    async def create_bucket(self, name: str) -> dict[str, Any]:
        body: dict[str, Any] = {"name": name}
        if self.jurisdiction and self.jurisdiction != "default":
            body["jurisdiction"] = self.jurisdiction
        payload = await request_json(
            self.http_client, service="Cloudflare R2", method="POST",
            url=f"{self._base()}/r2/buckets", headers=self.headers(), json_body=body,
        )
        return payload.get("result", {}) if isinstance(payload, dict) else {}

    async def delete_bucket(self, name: str) -> None:
        await request_json(
            self.http_client, service="Cloudflare R2", method="DELETE",
            url=f"{self._base()}/r2/buckets/{name}", headers=self.headers(),
        )

    async def create_bucket_credentials(self, bucket_name: str, *, label: str) -> dict[str, str]:
        """Mint a bucket-scoped S3 credential via the Tokens API. Returns
        {access_key_id, secret_access_key, endpoint} — the secret is derivable ONCE."""
        if not self.permission_group_id:
            raise ProviderAPIError(
                service="Cloudflare R2",
                message="R2 credential issuance is not configured (permission group id missing).",
                status_code=400,
            )
        resource = (
            f"com.cloudflare.edge.r2.bucket."
            f"{self.account_id}_{self.jurisdiction}_{bucket_name}"
        )
        body = {
            "name": label,
            "policies": [
                {
                    "effect": "allow",
                    "permission_groups": [{"id": self.permission_group_id}],
                    "resources": {resource: "*"},
                }
            ],
        }
        payload = await request_json(
            self.http_client, service="Cloudflare R2", method="POST",
            url=f"{self._base()}/tokens", headers=self.headers(), json_body=body,
        )
        result = payload.get("result", {}) if isinstance(payload, dict) else {}
        token_id = str(result.get("id") or "")
        token_value = str(result.get("value") or "")
        secret = hashlib.sha256(token_value.encode()).hexdigest() if token_value else ""
        return {
            "access_key_id": token_id,
            "secret_access_key": secret,
            "endpoint": self.s3_endpoint,
        }


__all__ = ["CLOUDFLARE_API", "R2Client", "ProviderAPIError"]
