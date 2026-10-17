from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.resumen.schemas import (
    ResumenAdminResponse,
    ResumenCajeroResponse,
    ResumenClienteResponse,
)
from app.domains.resumen.services import ResumenService
from app.shared.enums import Role
from app.shared.schemas.errors import ErrorResponse


router = APIRouter(prefix="/resumen", tags=["Resumen"])
ERROR_RESPONSES = {
    code: {"model": ErrorResponse} for code in (401, 403, 404, 500)
}


def _error_responses(*codes: int) -> dict[int, dict[str, object]]:
    return {code: ERROR_RESPONSES[code] for code in codes}


@router.get(
    "/cliente",
    response_model=ResumenClienteResponse,
    summary="Resumen de inicio del cliente en sesión",
    responses=_error_responses(401, 403, 404, 500),
)
async def get_resumen_cliente(
    current_user: Annotated[CurrentUser, Depends(require_role(Role.CLIENTE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ResumenClienteResponse:
    return await ResumenService.get_cliente(db_session, current_user.id)


@router.get(
    "/admin",
    response_model=ResumenAdminResponse,
    summary="Resumen de inicio para owner y admin",
    responses=_error_responses(401, 403, 500),
)
async def get_resumen_admin(
    current_user: Annotated[
        CurrentUser,
        Depends(require_role(Role.OWNER, Role.ADMIN)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumenAdminResponse:
    return await ResumenService.get_admin(db_session, settings)


@router.get(
    "/cajero",
    response_model=ResumenCajeroResponse,
    summary="Resumen de inicio del cajero en sesión",
    responses=_error_responses(401, 403, 500),
)
async def get_resumen_cajero(
    current_user: Annotated[CurrentUser, Depends(require_role(Role.CAJERO))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ResumenCajeroResponse:
    return await ResumenService.get_cajero(db_session, current_user.id, settings)
