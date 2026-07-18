"""OIDC IdP endpoints. Discovery + JWKS + userinfo are public; /authorize and
/launch require a live Tetra session (session-cookie auth); /token authenticates
the Mailcow client by its secret. See service.py for the end-to-end flow."""

from __future__ import annotations

import base64
import binascii
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db_session
from app.models import AdminUser
from app.modules.mail.service import MailService
from app.modules.oidc.service import OIDCError, OIDCService
from app.routes.deps import require_admin

router = APIRouter(tags=["oidc"])


def _error_response(exc: OIDCError) -> JSONResponse:
    body = {"error": exc.error}
    if exc.description:
        body["error_description"] = exc.description
    headers = {"Cache-Control": "no-store", "Pragma": "no-cache"}
    if exc.status_code == 401:
        headers["WWW-Authenticate"] = 'Bearer error="%s"' % exc.error
    return JSONResponse(body, status_code=exc.status_code, headers=headers)


@router.get("/.well-known/openid-configuration")
async def openid_configuration(request: Request) -> JSONResponse:
    service = OIDCService(request)
    if not service.is_configured():
        return _error_response(
            OIDCError("temporarily_unavailable", "OIDC is not configured.", status_code=404)
        )
    return JSONResponse(service.discovery_document(), headers={"Cache-Control": "no-store"})


@router.get("/oidc/jwks")
async def jwks(request: Request) -> JSONResponse:
    service = OIDCService(request)
    if not service.is_configured():
        return _error_response(
            OIDCError("temporarily_unavailable", "OIDC is not configured.", status_code=404)
        )
    # Public keys are cacheable; help Mailcow avoid refetching on every login.
    return JSONResponse(service.jwks(), headers={"Cache-Control": "public, max-age=3600"})


@router.get("/oidc/launch")
async def launch(
    request: Request,
    mailbox: str,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_admin),
) -> RedirectResponse:
    """The console's "Open webmail" entrypoint. Verifies the tenant owns the
    mailbox, stashes it in the session, then bounces to Mailcow's OIDC login."""
    service = OIDCService(request)
    if not service.is_configured() or not service.settings.oidc_webmail_url:
        # Nothing to launch into — send the operator back to the mail page.
        return RedirectResponse("/mail", status_code=status.HTTP_303_SEE_OTHER)

    mail = MailService(request)
    if not await mail._mailbox_accessible(session, current_admin.tenant_id, mailbox):
        # Don't leak which mailboxes exist — same redirect as an unknown one.
        return RedirectResponse("/mail", status_code=status.HTTP_303_SEE_OTHER)

    display = next(
        (m.name for m in await mail.client.list_mailboxes() if m.username == mailbox),
        "",
    )
    service.set_selected_mailbox(mailbox, display)
    return RedirectResponse(
        service.settings.oidc_webmail_url, status_code=status.HTTP_303_SEE_OTHER
    )


@router.get("/oidc/authorize", response_model=None)
async def authorize(
    request: Request,
    client_id: str,
    redirect_uri: str,
    response_type: str = "code",
    scope: str = "openid",
    state: str | None = None,
    nonce: str | None = None,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_admin),
) -> RedirectResponse | JSONResponse:
    service = OIDCService(request)
    try:
        service._require_configured()
        # Validate the client + redirect_uri BEFORE trusting redirect_uri enough
        # to send errors to it (open-redirect defense).
        service.validate_client_id(client_id)
        service.validate_redirect_uri(redirect_uri)
    except OIDCError as exc:
        return _error_response(exc)

    def redirect_error(error: str, description: str = "") -> RedirectResponse:
        params = {"error": error, "state": state} if state else {"error": error}
        if description:
            params["error_description"] = description
        sep = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(
            f"{redirect_uri}{sep}{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER
        )

    if response_type != "code":
        return redirect_error("unsupported_response_type")

    selected = service.take_selected_mailbox()
    if not selected:
        return redirect_error(
            "access_denied", "Open your mailbox from the Tetra console first."
        )

    mailbox = selected["username"]
    mail = MailService(request)
    # Re-verify ownership at authorize time — the session selection is a hint,
    # never the authority; a revoked mailbox must fail here.
    if not await mail._mailbox_accessible(session, current_admin.tenant_id, mailbox):
        return redirect_error("access_denied", "You no longer have access to this mailbox.")

    code = await service.issue_code(
        mailbox=mailbox,
        name=selected.get("name") or mailbox,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        nonce=nonce,
    )
    params = {"code": code}
    if state:
        params["state"] = state
    sep = "&" if "?" in redirect_uri else "?"
    return RedirectResponse(
        f"{redirect_uri}{sep}{urlencode(params)}", status_code=status.HTTP_303_SEE_OTHER
    )


def _basic_auth_client(request: Request) -> tuple[str, str] | None:
    header = request.headers.get("Authorization", "")
    if not header.startswith("Basic "):
        return None
    try:
        decoded = base64.b64decode(header[6:]).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    cid, secret = decoded.split(":", 1)
    return cid, secret


@router.post("/oidc/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(...),
    redirect_uri: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
) -> JSONResponse:
    service = OIDCService(request)
    try:
        if grant_type != "authorization_code":
            raise OIDCError("unsupported_grant_type", "Only authorization_code is supported.")
        # Client auth: prefer HTTP Basic, fall back to form body (both per RFC 6749).
        basic = _basic_auth_client(request)
        cid = basic[0] if basic else (client_id or "")
        secret = basic[1] if basic else (client_secret or "")
        result = await service.exchange_code(
            code=code, client_id=cid, client_secret=secret, redirect_uri=redirect_uri
        )
    except OIDCError as exc:
        return _error_response(exc)
    return JSONResponse(
        result, headers={"Cache-Control": "no-store", "Pragma": "no-cache"}
    )


@router.get("/oidc/userinfo")
async def userinfo(request: Request) -> JSONResponse:
    service = OIDCService(request)
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return _error_response(
            OIDCError("invalid_token", "Missing bearer token.", status_code=401)
        )
    try:
        claims = await service.userinfo(header[7:].strip())
    except OIDCError as exc:
        return _error_response(exc)
    return JSONResponse(claims, headers={"Cache-Control": "no-store"})
