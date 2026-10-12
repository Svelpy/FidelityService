from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.negocio.schemas import (
    NegocioCreate,
    NegocioResponse,
    NegocioResponseAudit,
    NegocioUpdate,
)
from app.domains.negocio.services import NegocioService
from app.shared.enums import Action, Module, TipoNegocio
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/negocios", tags=["Negocios"])

ERROR_RESPONSES = {
    400: {"model": ErrorResponse},
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
    response_model=PaginatedResponse[NegocioResponse],
    summary="Listar negocios",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_negocios(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    tipo: Annotated[TipoNegocio | None, Query()] = None,
) -> PaginatedResponse[NegocioResponse]:
    return await NegocioService.list(
        db_session,
        page=page,
        per_page=per_page,
        tipo=tipo,
    )


@router.post(
    "/",
    response_model=NegocioResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Crear negocio",
    responses=_error_responses(401, 403, 409, 422, 500),
)
async def create_negocio(
    data: NegocioCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> NegocioResponseAudit:
    return await NegocioService.create(
        db_session,
        data,
        actor_id=current_user.id,
    )


@router.post(
    "/{negocio_id}/image",
    response_model=NegocioResponseAudit,
    summary="Subir o reemplazar imagen de negocio",
    responses=_error_responses(400, 401, 403, 404, 422, 500),
)
async def upload_negocio_image(
    negocio_id: UUID,
    file: Annotated[UploadFile, File(description="Imagen del negocio")],
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> NegocioResponseAudit:
    return await NegocioService.upload_image(
        db_session,
        negocio_id,
        file,
        actor_id=current_user.id,
        settings=settings,
    )


@router.delete(
    "/{negocio_id}/image",
    response_model=NegocioResponseAudit,
    summary="Eliminar imagen de negocio",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def delete_negocio_image(
    negocio_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> NegocioResponseAudit:
    return await NegocioService.delete_image(
        db_session,
        negocio_id,
        actor_id=current_user.id,
    )


@router.get(
    "/{negocio_id}",
    response_model=NegocioResponseAudit,
    summary="Consultar negocio",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_negocio(
    negocio_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> NegocioResponseAudit:
    return await NegocioService.get(db_session, negocio_id)


@router.patch(
    "/{negocio_id}",
    response_model=NegocioResponseAudit,
    summary="Actualizar negocio",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def update_negocio(
    negocio_id: UUID,
    data: NegocioUpdate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> NegocioResponseAudit:
    return await NegocioService.update(
        db_session,
        negocio_id,
        data,
        actor_id=current_user.id,
    )


@router.delete(
    "/{negocio_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar negocio",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def delete_negocio(
    negocio_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.NEGOCIO, Action.DELETE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await NegocioService.delete(
        db_session,
        negocio_id,
        actor_id=current_user.id,
    )
