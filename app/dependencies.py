from fastapi import Request
from fastapi.responses import RedirectResponse


async def require_login(request: Request):
    if request.state.current_user is None:
        return RedirectResponse("/auth/login", status_code=303)
    return None
