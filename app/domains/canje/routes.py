from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission, require_role
from app.domains.auth.schemas import CurrentUser
from app.domains.canje.schemas import (
    CanjeByCodigoResponse,
    CanjeCreate,
    CanjeDetailResponse,
    CanjeDetailResponseAudit,
    CanjeExpireResponse,
    CanjeListResponse,
    CanjeResponseAudit,
    CanjeResponse,
)
from app.domains.canje.services import CanjeService
from app.shared.enums import Action, EstadoCanje, Module, Role
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/canjes", tags=["Canjes"])

ERROR_RESPONSES = {
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
}


def _error_responses(*status_codes: int) -> dict[int, dict[str, object]]:
    return {status_code: ERROR_RESPONSES[status_code] for status_code in status_codes}


@router.get(
    "/",
    response_model=PaginatedResponse[CanjeListResponse],
    summary="Listar canjes visibles",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_canjes(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    cliente_id: Annotated[UUID | None, Query()] = None,
    dador_id: Annotated[UUID | None, Query()] = None,
    vale_id: Annotated[UUID | None, Query()] = None,
    status_filter: Annotated[EstadoCanje | None, Query(alias="status")] = None,
    sucursal_id: Annotated[UUID | None, Query()] = None,
    negocio_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[CanjeListResponse]:
    return await CanjeService.list(
        db_session,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
        page=page,
        per_page=per_page,
        cliente_id=cliente_id,
        dador_id=dador_id,
        vale_id=vale_id,
        status=status_filter,
        sucursal_id=sucursal_id,
        negocio_id=negocio_id,
    )


@router.get(
    "/me",
    response_model=PaginatedResponse[CanjeListResponse],
    summary="Listar mis canjes como cliente o dador",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_my_canjes(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    status_filter: Annotated[EstadoCanje | None, Query(alias="status")] = None,
    vale_id: Annotated[UUID | None, Query()] = None,
    negocio_id: Annotated[UUID | None, Query()] = None,
    sucursal_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[CanjeListResponse]:
    return await CanjeService.list_for_user(
        db_session,
        current_user.id,
        page=page,
        per_page=per_page,
        status=status_filter,
        vale_id=vale_id,
        negocio_id=negocio_id,
        sucursal_id=sucursal_id,
    )


@router.post(
    "/",
    response_model=CanjeResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Solicitar canje de un vale",
    responses=_error_responses(401, 403, 404, 409, 422, 503, 500),
)
async def create_canje(
    data: CanjeCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeResponseAudit:
    return await CanjeService.create(
        db_session,
        data,
        current_user.id,
        current_user.role,
    )


@router.post(
    "/expire",
    response_model=CanjeExpireResponse,
    summary="Expirar canjes pendientes vencidos",
    responses=_error_responses(401, 403, 500),
)
async def expire_canjes(
    current_user: Annotated[
        CurrentUser,
        Depends(
            require_role(
                Role.SUPERADMIN,
                Role.OWNER,
                Role.ADMIN,
                Role.CAJERO,
            )
        ),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeExpireResponse:
    return await CanjeService.expire_pending(
        db_session,
        actor_id=current_user.id,
    )


@router.post(
    "/{canje_id}/redeem",
    response_model=CanjeByCodigoResponse,
    summary="Confirmar un canje mediante su identificador",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def redeem_canje(
    canje_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeByCodigoResponse:
    return await CanjeService.redeem(
        db_session,
        canje_id,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
    )


@router.get(
    "/codigo/{codigo_canje}",
    response_model=CanjeByCodigoResponse,
    summary="Consultar canje por código",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_canje_by_codigo(
    codigo_canje: Annotated[
        str,
        Path(min_length=8, max_length=8, pattern=r"^[0-9]{8}$"),
    ],
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeByCodigoResponse:
    return await CanjeService.get_by_codigo(
        db_session,
        codigo_canje,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
    )


@router.get(
    "/{canje_id}",
    response_model=CanjeDetailResponse,
    summary="Consultar canje",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_canje(
    canje_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeDetailResponse:
    return await CanjeService.get(
        db_session,
        canje_id,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
    )


@router.get(
    "/{canje_id}/audit",
    response_model=CanjeDetailResponseAudit,
    summary="Consultar canje con auditoría",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_canje_audit(
    canje_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_role(Role.SUPERADMIN, Role.OWNER, Role.ADMIN)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeDetailResponseAudit:
    return await CanjeService.get_audit(
        db_session,
        canje_id,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
    )


@router.post(
    "/{canje_id}/cancel",
    response_model=CanjeResponse,
    summary="Cancelar canje pendiente",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def cancel_canje(
    canje_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CANJE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CanjeResponseAudit:
    return await CanjeService.cancel(
        db_session,
        canje_id,
        current_user.id,
        current_user.role,
        current_user.sucursal_id,
    )
