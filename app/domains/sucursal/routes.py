from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.sucursal.schemas import (
    SucursalCreate,
    SucursalResponse,
    SucursalResponseAudit,
    SucursalUpdate,
)
from app.domains.sucursal.services import SucursalService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/sucursales", tags=["Sucursales"])

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
    "/",
    response_model=PaginatedResponse[SucursalResponse],
    summary="Listar sucursales",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_sucursales(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.SUCURSAL, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    negocio_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[SucursalResponse]:
    return await SucursalService.list(
        db_session,
        page=page,
        per_page=per_page,
        negocio_id=negocio_id,
    )


@router.post(
    "/",
    response_model=SucursalResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Crear sucursal",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def create_sucursal(
    data: SucursalCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.SUCURSAL, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> SucursalResponseAudit:
    return await SucursalService.create(
        db_session,
        data,
        actor_id=current_user.id,
    )


@router.get(
    "/{sucursal_id}",
    response_model=SucursalResponseAudit,
    summary="Consultar sucursal",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_sucursal(
    sucursal_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.SUCURSAL, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> SucursalResponseAudit:
    return await SucursalService.get(db_session, sucursal_id)


@router.patch(
    "/{sucursal_id}",
    response_model=SucursalResponseAudit,
    summary="Actualizar sucursal",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def update_sucursal(
    sucursal_id: UUID,
    data: SucursalUpdate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.SUCURSAL, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> SucursalResponseAudit:
    return await SucursalService.update(
        db_session,
        sucursal_id,
        data,
        actor_id=current_user.id,
    )


@router.delete(
    "/{sucursal_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar sucursal",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def delete_sucursal(
    sucursal_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.SUCURSAL, Action.DELETE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await SucursalService.delete(
        db_session,
        sucursal_id,
        actor_id=current_user.id,
    )
