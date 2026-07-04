from urllib.parse import unquote

from fastapi import APIRouter, Depends, Form, Request, status
from pydantic import ValidationError
from fastapi.responses import RedirectResponse

from app.modules.auth.schemas import LoginFormData
from app.modules.auth.service import AuthService
from app.routes import ensure_csrf_token, get_current_admin
from app.routes.deps import get_auth_service, verify_csrf_token
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login_form(
    request: Request,
    current_admin=Depends(get_current_admin),
):
    if current_admin is not None:
        return RedirectResponse("/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    next_url = request.query_params.get("next", "/dashboard")
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "error": None,
            "next_url": next_url,
            "csrf_token": ensure_csrf_token(request),
        },
    )


@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    csrf_token: str = Form(...),
    next_url: str = Form("/dashboard"),
    auth_service: AuthService = Depends(get_auth_service),
):
    limiter = request.app.state.rate_limiter
    client_host = request.client.host if request.client else "unknown"
    decision = await limiter.check(
        f"login:{client_host}",
        limit=request.state.settings.login_rate_limit_attempts,
        window_seconds=request.state.settings.login_rate_limit_window_seconds,
    )
    if not decision.allowed:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": f"Too many login attempts. Try again in {decision.retry_after_seconds}s.",
                "next_url": next_url,
                "csrf_token": ensure_csrf_token(request),
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    try:
        form_data = LoginFormData(email=email, password=password, csrf_token=csrf_token)
        verify_csrf_token(request, form_data.csrf_token)
    except ValidationError as exc:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": exc.errors()[0]["msg"],
                "next_url": next_url,
                "csrf_token": ensure_csrf_token(request),
            },
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    admin = await auth_service.authenticate(form_data.email, form_data.password)
    if admin is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "error": "Invalid credentials.",
                "next_url": next_url,
                "csrf_token": ensure_csrf_token(request),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    await auth_service.touch_last_login(admin)
    request.session.clear()
    request.session["admin_user_id"] = admin.id
    request.session["admin_email"] = admin.email
    request.session["admin_name"] = admin.full_name
    request.session["role"] = admin.role
    request.session["tenant_id"] = admin.tenant_id
    request.session["tenant_slug"] = admin.tenant.slug if admin.tenant else ""
    request.session["tenant_name"] = admin.tenant.name if admin.tenant else ""
    ensure_csrf_token(request)

    destination = unquote(next_url) if next_url.startswith("/") else "/dashboard"
    return RedirectResponse(destination, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/logout")
async def logout(request: Request, csrf_token: str = Form(...)):
    verify_csrf_token(request, csrf_token)
    request.session.clear()
    return RedirectResponse("/auth/login", status_code=status.HTTP_303_SEE_OTHER)