import asyncio

from fastapi import APIRouter, Depends, Form, Request, status
from fastapi.responses import RedirectResponse

from app.models import AdminUser
from app.routes.deps import require_admin, verify_csrf_token
from app.templating import build_templates

templates = build_templates()
router = APIRouter(prefix="/maintenance", tags=["maintenance"])

COOLIFY_SSH = "root@65.21.238.89"
COOLIFY_CONTAINER = "coolify"

ALLOWED_COMMANDS: list[dict[str, str]] = [
    {"cmd": "cleanup:stucked-resources", "label": "Cleanup Stuck Resources", "desc": "Remove resources stuck in a transitional state."},
    {"cmd": "cleanup:deployment-queue", "label": "Cleanup Deployment Queue", "desc": "Purge stale entries from the deployment queue."},
    {"cmd": "cleanup:database", "label": "Cleanup Database", "desc": "Run database cleanup and pruning tasks."},
    {"cmd": "cleanup:redis", "label": "Cleanup Redis", "desc": "Flush stale Redis cache entries."},
    {"cmd": "check:deployment-queue", "label": "Check Deployment Queue", "desc": "Inspect the current deployment queue status."},
    {"cmd": "schedule:run-manual", "label": "Run Manual Schedule", "desc": "Trigger the manual schedule runner."},
    {"cmd": "down", "label": "Maintenance Mode ON", "desc": "Put Coolify into maintenance mode."},
    {"cmd": "up", "label": "Maintenance Mode OFF", "desc": "Take Coolify out of maintenance mode."},
]

ALLOWED_CMD_NAMES = {c["cmd"] for c in ALLOWED_COMMANDS}


async def _run_artisan(command: str) -> tuple[int, str]:
    """Run an artisan command on the Coolify server via SSH."""
    proc = await asyncio.create_subprocess_exec(
        "ssh", COOLIFY_SSH,
        "docker", "exec", COOLIFY_CONTAINER,
        "php", "artisan", command, "--no-interaction",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    return proc.returncode or 0, stdout.decode(errors="replace")


@router.get("")
async def maintenance_page(
    request: Request,
    current_admin: AdminUser = Depends(require_admin),
):
    return templates.TemplateResponse(
        request,
        "maintenance/index.html",
        {
            "commands": ALLOWED_COMMANDS,
            "result": request.query_params.get("result"),
            "result_cmd": request.query_params.get("result_cmd"),
            "result_code": request.query_params.get("result_code"),
            "error": request.query_params.get("error"),
        },
    )


@router.post("/run")
async def run_command(
    request: Request,
    command: str = Form(...),
    csrf_token: str = Form(...),
    current_admin: AdminUser = Depends(require_admin),
):
    verify_csrf_token(request, csrf_token)
    if command not in ALLOWED_CMD_NAMES:
        return RedirectResponse(f"/maintenance?error=Command+not+allowed:+{command}", status_code=status.HTTP_303_SEE_OTHER)
    try:
        code, output = await _run_artisan(command)
        from urllib.parse import quote
        return RedirectResponse(
            f"/maintenance?result={quote(output[:2000])}&result_cmd={quote(command)}&result_code={code}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    except Exception as exc:
        from urllib.parse import quote
        return RedirectResponse(f"/maintenance?error={quote(str(exc)[:500])}", status_code=status.HTTP_303_SEE_OTHER)
