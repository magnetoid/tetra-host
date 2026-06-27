from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse

from app.config import get_settings
from app.security import SessionUser, create_session_token, verify_password
from app.services.tenants import authenticate_user
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.get("/login")
async def login_form(request: Request):
    if request.state.current_user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    user = authenticate_user(email)
    if user and verify_password(password, user.password_hash):
        token = create_session_token(
            SessionUser(user_id=user.id, tenant_id=user.tenant_id, email=user.email, role=user.role)
        )
        response = RedirectResponse("/dashboard", status_code=303)
        response.set_cookie(
            key=settings.session_cookie_name,
            value=token,
            httponly=True,
            secure=settings.session_https_only,
            samesite="lax",
            max_age=60 * 60 * 12,
        )
        return response
    return templates.TemplateResponse(request, "auth/login.html", {"error": "Invalid login"}, status_code=401)


@router.post("/logout")
async def logout():
    response = RedirectResponse("/auth/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
