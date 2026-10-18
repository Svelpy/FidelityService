from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.movimientos_puntos.schemas import (
    MovimientoPuntosDetailResponse,
    MovimientoPuntosListMeResponse,
    MovimientoPuntosListResponse,
)
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.shared.enums import Action, Module, TipoMovimiento
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(
    prefix="/movimientos-puntos",
    tags=["Movimientos de puntos"],
)

ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}


def _error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {status_code: ERROR_RESPONSES[status_code] for status_code in status_codes}


@router.get(
    "/me",
    response_model=PaginatedResponse[MovimientoPuntosListMeResponse],
    summary="Listar mis movimientos de puntos",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_my_movimientos_puntos(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.MOVIMIENTOS_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    tipo: Annotated[TipoMovimiento | None, Query()] = None,
) -> PaginatedResponse[MovimientoPuntosListMeResponse]:
    return await MovimientoPuntosService.list_me(
        db_session,
        current_user.id,
        page=page,
        per_page=per_page,
        movement_type=tipo,
    )


@router.get(
    "/",
    response_model=PaginatedResponse[MovimientoPuntosListResponse],
    summary="Listar movimientos de puntos",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_movimientos_puntos(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.MOVIMIENTOS_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    usuario_id: Annotated[UUID | None, Query()] = None,
    tipo: Annotated[TipoMovimiento | None, Query()] = None,
) -> PaginatedResponse[MovimientoPuntosListResponse]:
    return await MovimientoPuntosService.list(
        db_session,
        current_user.role,
        page=page,
        per_page=per_page,
        user_id=usuario_id,
        movement_type=tipo,
    )


@router.get(
    "/{movimiento_id}",
    response_model=MovimientoPuntosDetailResponse,
    summary="Consultar detalle de un movimiento de puntos",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_movimiento_puntos(
    movimiento_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.MOVIMIENTOS_PUNTOS, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> MovimientoPuntosDetailResponse:
    return await MovimientoPuntosService.get_detail(
        db_session,
        movimiento_id,
        current_user.id,
        current_user.role,
    )
