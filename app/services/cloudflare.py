from dataclasses import dataclass

from app.config import get_settings


@dataclass
class CloudflareClient:
    api_token: str

    @classmethod
    def from_settings(cls) -> "CloudflareClient":
        return cls(api_token=get_settings().cloudflare_api_token)
