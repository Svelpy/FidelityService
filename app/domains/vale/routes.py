from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.vale.schemas import (
    ValeCreate,
    ValePuntosSuggestionRequest,
    ValePuntosSuggestionResponse,
    ValeResponse,
    ValeResponseAudit,
    ValeUpdate,
)
from app.domains.vale.services import ValeService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/vales", tags=["Vales"])
ERROR_RESPONSES = {
    code: {"model": ErrorResponse} for code in (400, 401, 403, 404, 409, 422, 500)
}


def _error_responses(*codes: int) -> dict[int, dict[str, object]]:
    return {code: ERROR_RESPONSES[code] for code in codes}


@router.post(
    "/sugerir-puntos",
    response_model=ValePuntosSuggestionResponse,
    summary="Calcular puntos sugeridos para un vale",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def suggest_vale_points(
    data: ValePuntosSuggestionRequest,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ValePuntosSuggestionResponse:
    return await ValeService.suggest_points(db_session, data.total_costo)


@router.get(
    "/",
    response_model=PaginatedResponse[ValeResponse],
    summary="Listar vales",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_vales(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
    categoria_id: Annotated[UUID | None, Query()] = None,
    negocio_id: Annotated[UUID | None, Query()] = None,
) -> PaginatedResponse[ValeResponse]:
    return await ValeService.list(
        db_session,
        page=page,
        per_page=per_page,
        categoria_id=categoria_id,
        negocio_id=negocio_id,
    )


@router.post(
    "/",
    response_model=ValeResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Crear vale",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def create_vale(
    data: ValeCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ValeResponseAudit:
    return await ValeService.create(db_session, data, actor_id=current_user.id)


@router.post(
    "/{vale_id}/image",
    response_model=ValeResponseAudit,
    summary="Subir o reemplazar imagen de vale",
    responses=_error_responses(400, 401, 403, 404, 422, 500),
)
async def upload_vale_image(
    vale_id: UUID,
    file: Annotated[UploadFile, File(description="Imagen del vale")],
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ValeResponseAudit:
    return await ValeService.upload_image(
        db_session, vale_id, file, current_user.id, settings
    )


@router.delete(
    "/{vale_id}/image",
    response_model=ValeResponseAudit,
    summary="Eliminar imagen de vale",
    responses=_error_responses(401, 403, 404, 500),
)
async def delete_vale_image(
    vale_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ValeResponseAudit:
    return await ValeService.delete_image(db_session, vale_id, current_user.id)


@router.get(
    "/{vale_id}",
    response_model=ValeResponseAudit,
    summary="Consultar vale",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_vale(
    vale_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ValeResponseAudit:
    return await ValeService.get(db_session, vale_id)


@router.patch(
    "/{vale_id}",
    response_model=ValeResponseAudit,
    summary="Actualizar vale",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def update_vale(
    vale_id: UUID,
    data: ValeUpdate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> ValeResponseAudit:
    return await ValeService.update(
        db_session, vale_id, data, actor_id=current_user.id
    )


@router.delete(
    "/{vale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar vale",
    responses=_error_responses(401, 403, 404, 500),
)
async def delete_vale(
    vale_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.DELETE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await ValeService.delete(db_session, vale_id, current_user.id)
