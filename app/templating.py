from pathlib import Path

from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

from app.config import get_settings


def template_paths() -> list[str]:
    settings = get_settings()
    paths: list[str] = []

    if settings.template_search_path:
        paths.extend([p for p in settings.template_search_path.split(":") if p])

    themed = Path("app/themes") / settings.theme / "templates"
    if themed.exists():
        paths.append(str(themed))

    paths.append("app/templates")
    return paths


def build_templates() -> Jinja2Templates:
    templates = Jinja2Templates(directory="app/templates")
    templates.env.loader = ChoiceLoader([FileSystemLoader(p) for p in template_paths()])
    return templates
