from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.config_puntos.schemas import (
    ConfigPuntosCreate,
    ConfigPuntosResponse,
    ConfigPuntosResponseAudit,
)
from app.domains.config_puntos.services import ConfigPuntosService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/config-puntos", tags=["Configuración de puntos"])

ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


def _error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {status_code: ERROR_RESPONSES[status_code] for status_code in status_codes}


@router.get(
    "/active",
    response_model=ConfigPuntosResponseAudit,
    summary="Consultar configuración de puntos activa",
    responses=_error_responses(401, 403, 404, 500),
)
async def get_active_config_puntos(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CONFIG_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ConfigPuntosResponseAudit:
    config = await ConfigPuntosService.get_active(db_session)
    assert config is not None
    return config


@router.get(
    "/",
    response_model=PaginatedResponse[ConfigPuntosResponse],
    summary="Listar historial de configuraciones de puntos",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_config_puntos(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CONFIG_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[ConfigPuntosResponse]:
    return await ConfigPuntosService.list(
        db_session,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/",
    response_model=ConfigPuntosResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Sustituir configuración de puntos activa",
    responses=_error_responses(401, 403, 409, 422, 500),
)
async def replace_config_puntos(
    data: ConfigPuntosCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CONFIG_PUNTOS, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ConfigPuntosResponseAudit:
    return await ConfigPuntosService.replace(
        db_session,
        data,
        actor_id=current_user.id,
    )


@router.get(
    "/{config_puntos_id}",
    response_model=ConfigPuntosResponseAudit,
    summary="Consultar configuración de puntos",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_config_puntos(
    config_puntos_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CONFIG_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ConfigPuntosResponseAudit:
    return await ConfigPuntosService.get(db_session, config_puntos_id)
