from typing import Any

from app.config import get_settings


class DeploymentNotifier:
    def __init__(self, http_client) -> None:
        self.http_client = http_client
        self.settings = get_settings()

    def is_configured(self) -> bool:
        return bool(self.settings.deploy_notify_webhook_url)

    async def notify(
        self,
        *,
        event: str,
        application_id: str,
        application_name: str,
        channel: str = "",
        sms_to: str = "",
        status: str = "",
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured() or event not in self.settings.deploy_notify_enabled_events:
            return {"ok": False, "skipped": True}

        selected_channel = channel or self.settings.deploy_notify_default_channel
        payload = {
            "event": event,
            "application_id": application_id,
            "application_name": application_name,
            "channel": selected_channel,
            "sms_to": sms_to or self.settings.deploy_notify_sms_to,
            "status": status or event,
            "details": details or {},
        }
        headers = {"Content-Type": "application/json"}
        if self.settings.deploy_notify_webhook_bearer_token:
            headers["Authorization"] = f"Bearer {self.settings.deploy_notify_webhook_bearer_token}"
        response = await self.http_client.post(
            self.settings.deploy_notify_webhook_url,
            json=payload,
            headers=headers,
        )
        response.raise_for_status()
        if not response.content:
            return {"ok": True}
        try:
            data = response.json()
            return data if isinstance(data, dict) else {"ok": True, "response": data}
        except Exception:
            return {"ok": True, "response": response.text[:500]}
