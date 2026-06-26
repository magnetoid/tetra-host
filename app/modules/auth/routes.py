from fastapi import APIRouter, Form, Request
from fastapi.responses import RedirectResponse
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login_form(request: Request):
    return templates.TemplateResponse(request, "auth/login.html", {"error": None})


@router.post("/login")
async def login(request: Request, email: str = Form(...), password: str = Form(...)):
    if email and password:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "auth/login.html", {"error": "Invalid login"})
