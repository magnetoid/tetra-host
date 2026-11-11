"""`/api/v1/importers` — platform-admin migration of existing apps onto the Tetra Engine.

This module owns its own API router (roadmap phase 1: new capabilities do not grow
``app/api/routes.py``). It reuses that module's auth dependencies.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes import require_platform_admin
from app.db.session import get_db_session
from app.models.admin import AdminUser
from app.models.import_run import ImportRun
from app.modules.importers.service import CoolifyImporter, ImporterError, spawn_background
from app.services.coolify import CoolifyClient

router = APIRouter(prefix="/api/v1/importers", tags=["api"])


class CoolifyImportRequest(BaseModel):
    app_uuid: str = Field(min_length=6, max_length=64)
    project: str = Field(min_length=1, max_length=50)
    stage_exclude: list[str] | None = None


class ImportRunSummary(BaseModel):
    id: str
    source: str
    source_ref: str
    project: str
    state: str
    error: str
    created_by: str
    created_at: str
    updated_at: str


class ImportRunDetail(ImportRunSummary):
    summary: dict
    log: str


def _summary(run: ImportRun) -> ImportRunSummary:
    return ImportRunSummary(
        id=run.id,
        source=run.source,
        source_ref=run.source_ref,
        project=run.project,
        state=run.state,
        error=run.error,
        created_by=run.created_by,
        created_at=run.created_at.isoformat(),
        updated_at=run.updated_at.isoformat(),
    )


def _detail(run: ImportRun) -> ImportRunDetail:
    return ImportRunDetail(**_summary(run).model_dump(), summary=run.summary or {}, log=run.log)


def _importer(request: Request) -> CoolifyImporter:
    coolify = CoolifyClient.from_settings(
        http_client=request.app.state.http_client, cache=request.app.state.cache
    )
    return CoolifyImporter(coolify=coolify)


@router.get("/runs", response_model=list[ImportRunSummary])
async def api_list_import_runs(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> list[ImportRunSummary]:
    runs = await _importer(request).list_runs(session, current_admin.tenant_id)
    return [_summary(run) for run in runs]


@router.get("/runs/{run_id}", response_model=ImportRunDetail)
async def api_get_import_run(
    run_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> ImportRunDetail:
    try:
        run = await _importer(request).get_run(session, current_admin.tenant_id, run_id)
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _detail(run)


@router.post("/coolify", response_model=ImportRunDetail)
async def api_plan_coolify_import(
    payload: CoolifyImportRequest,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> ImportRunDetail:
    try:
        run = await _importer(request).plan(
            session,
            tenant_id=current_admin.tenant_id,
            actor=current_admin.email,
            app_uuid=payload.app_uuid,
            project=payload.project,
            stage_exclude=payload.stage_exclude,
        )
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return _detail(run)


@router.post("/runs/{run_id}/{action}", response_model=ImportRunDetail)
async def api_import_action(
    run_id: str,
    action: Literal["stage", "cutover", "rollback"],
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    current_admin: AdminUser = Depends(require_platform_admin),
) -> ImportRunDetail:
    importer = _importer(request)
    try:
        run = await importer.request(
            session,
            tenant_id=current_admin.tenant_id,
            actor=current_admin.email,
            run_id=run_id,
            action=action,
        )
    except ImporterError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    # Commit the claimed state before the background step opens its own session.
    await session.commit()
    spawn_background(importer.execute(run.id, action))
    return _detail(run)
