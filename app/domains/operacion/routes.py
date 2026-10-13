from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.operacion.schemas import (
    OperacionCreate,
    OperacionResponse,
    OperacionResponseAudit,
)
from app.domains.operacion.services import OperacionService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/operaciones", tags=["Operaciones"])

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
    response_model=PaginatedResponse[OperacionResponse],
    summary="Listar operaciones visibles",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_operaciones(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.OPERACION, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    emisor_id: Annotated[UUID | None, Query()] = None,
    receptor_id: Annotated[UUID | None, Query()] = None,
    sucursal_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[OperacionResponse]:
    return await OperacionService.list(
        db_session,
        current_user.id,
        current_user.role,
        page=page,
        per_page=per_page,
        emisor_id=emisor_id,
        receptor_id=receptor_id,
        sucursal_id=sucursal_id,
    )


@router.get(
    "/{operation_id}",
    response_model=OperacionResponseAudit,
    summary="Consultar operación",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_operacion(
    operation_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.OPERACION, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> OperacionResponseAudit:
    return await OperacionService.get(
        db_session,
        operation_id,
        current_user.id,
        current_user.role,
    )


@router.post(
    "/",
    response_model=OperacionResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar compra y acumular puntos",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def create_operacion(
    data: OperacionCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.OPERACION, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> OperacionResponseAudit:
    return await OperacionService.create(
        db_session,
        data,
        current_user.id,
        current_user.sucursal_id,
    )
