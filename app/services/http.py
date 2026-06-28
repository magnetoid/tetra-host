import asyncio
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class ProviderAPIError(Exception):
    service: str
    message: str
    status_code: int | None = None

    def __str__(self) -> str:
        return self.message


async def request_json(
    client: httpx.AsyncClient,
    *,
    service: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> Any:
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
            )
        except (httpx.ConnectError, httpx.ReadTimeout, httpx.RemoteProtocolError) as exc:
            last_error = exc
            if attempt == max_attempts:
                break
            await asyncio.sleep(0.25 * attempt)
            continue

        if response.status_code in {429, 500, 502, 503, 504} and attempt < max_attempts:
            retry_after = response.headers.get("retry-after")
            delay = float(retry_after) if retry_after and retry_after.isdigit() else 0.5 * attempt
            await asyncio.sleep(delay)
            continue

        if response.is_error:
            raise ProviderAPIError(
                service=service,
                message=f"{service} request failed: {response.text[:300]}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        return response.json()

    raise ProviderAPIError(service=service, message=f"{service} request failed.") from last_error
