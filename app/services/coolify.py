from dataclasses import dataclass

import httpx

from app.config import get_settings


@dataclass
class CoolifyClient:
    base_url: str
    token: str

    @classmethod
    def from_settings(cls) -> "CoolifyClient":
        s = get_settings()
        return cls(base_url=s.coolify_url.rstrip("/"), token=s.coolify_token)

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}

    async def list_projects(self) -> list[dict]:
        if not self.base_url or not self.token:
            return []
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get(f"{self.base_url}/api/v1/projects", headers=self.headers())
            r.raise_for_status()
            return r.json()

    def placeholder_sites(self) -> list[dict[str, str]]:
        return [
            {"name": "imbaproduction.com", "status": "planned", "runtime": "Plesk → Coolify"},
            {"name": "montenegro-experience.me", "status": "planned", "runtime": "Django/Coolify"},
            {"name": "dotbooks.store", "status": "planned", "runtime": "Django/Coolify"},
        ]
