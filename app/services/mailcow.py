from dataclasses import dataclass

from app.config import get_settings


@dataclass
class MailcowClient:
    base_url: str
    api_key: str

    @classmethod
    def from_settings(cls) -> "MailcowClient":
        s = get_settings()
        return cls(base_url=s.mailcow_url.rstrip("/"), api_key=s.mailcow_api_key)
