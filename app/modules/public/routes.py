from fastapi import APIRouter, Request
from app.templating import build_templates

templates = build_templates()
router = APIRouter()


@router.get("/")
async def landing(request: Request):
    return templates.TemplateResponse(request, "public/landing.html")
