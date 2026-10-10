from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import require_permission
from app.domains.auth.schemas import CurrentUser
from app.domains.categoria.schemas import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaResponseAudit,
    CategoriaUpdate,
)
from app.domains.categoria.services import CategoriaService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/categorias", tags=["Categorías"])

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
    response_model=PaginatedResponse[CategoriaResponse],
    summary="Listar categorías",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_categorias(
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CATEGORIA, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[CategoriaResponse]:
    return await CategoriaService.list(
        db_session,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{categoria_id}",
    response_model=CategoriaResponseAudit,
    summary="Consultar categoría",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_categoria(
    categoria_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CATEGORIA, Action.READ)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoriaResponseAudit:
    return await CategoriaService.get(db_session, categoria_id)


@router.post(
    "/",
    response_model=CategoriaResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Crear categoría",
    responses=_error_responses(401, 403, 409, 422, 500),
)
async def create_categoria(
    data: CategoriaCreate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CATEGORIA, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoriaResponseAudit:
    return await CategoriaService.create(
        db_session,
        data,
        actor_id=current_user.id,
    )


@router.patch(
    "/{categoria_id}",
    response_model=CategoriaResponseAudit,
    summary="Actualizar categoría",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def update_categoria(
    categoria_id: UUID,
    data: CategoriaUpdate,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CATEGORIA, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> CategoriaResponseAudit:
    return await CategoriaService.update(
        db_session,
        categoria_id,
        data,
        actor_id=current_user.id,
    )


@router.delete(
    "/{categoria_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar categoría",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def delete_categoria(
    categoria_id: UUID,
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.CATEGORIA, Action.DELETE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await CategoriaService.delete(
        db_session,
        categoria_id,
        actor_id=current_user.id,
    )
