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


async def _send_with_retries(
    client: httpx.AsyncClient,
    *,
    service: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    max_attempts: int = 3,
    timeout: float | None = None,
) -> httpx.Response:
    """Send a request with retry/backoff, raising ProviderAPIError on failure.

    Shared core for ``request_json`` and ``request_text``. Supports JSON
    (``json_body``) as well as form/multipart bodies (``data``/``files``) for
    providers whose write endpoints expect uploads (e.g. Cloudflare's BIND import).
    ``timeout`` overrides the client default per call (e.g. long LLM completions).
    """
    last_error: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_body,
                data=data,
                files=files,
                timeout=httpx.USE_CLIENT_DEFAULT if timeout is None else timeout,
            )
        except httpx.HTTPError as exc:
            # ALL transport failures (incl. ConnectTimeout/PoolTimeout/WriteTimeout/
            # ReadError) must surface as ProviderAPIError, never raw — callers'
            # best-effort paths catch ProviderAPIError only. Nothing here raises
            # HTTPStatusError (statuses are handled below).
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

        return response

    raise ProviderAPIError(service=service, message=f"{service} request failed.") from last_error


async def request_json(
    client: httpx.AsyncClient,
    *,
    service: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    json_body: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    max_attempts: int = 3,
    timeout: float | None = None,
) -> Any:
    response = await _send_with_retries(
        client,
        service=service,
        method=method,
        url=url,
        headers=headers,
        params=params,
        json_body=json_body,
        data=data,
        files=files,
        max_attempts=max_attempts,
        timeout=timeout,
    )
    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise ProviderAPIError(
            service=service,
            message=f"{service} returned invalid JSON.",
            status_code=response.status_code,
        ) from exc


async def request_text(
    client: httpx.AsyncClient,
    *,
    service: str,
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, Any] | None = None,
    max_attempts: int = 3,
) -> str:
    """Like ``request_json`` but returns the raw response body (e.g. BIND export)."""
    response = await _send_with_retries(
        client,
        service=service,
        method=method,
        url=url,
        headers=headers,
        params=params,
        max_attempts=max_attempts,
    )
    return response.text
