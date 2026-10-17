from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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


async def _parse_vale_create_form(
    total_costo: Annotated[Decimal, Form()],
    total_puntos: Annotated[int, Form()],
    nombre: Annotated[str, Form()],
    categoria_id: Annotated[UUID, Form()],
    negocio_id: Annotated[UUID, Form()],
    descripcion: Annotated[str | None, Form()] = None,
) -> ValeCreate:
    try:
        return ValeCreate(
            total_costo=total_costo,
            total_puntos=total_puntos,
            nombre=nombre,
            descripcion=descripcion,
            categoria_id=categoria_id,
            negocio_id=negocio_id,
        )
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


async def _parse_vale_update_form(
    request: Request,
    total_costo: Annotated[Decimal | None, Form()] = None,
    total_puntos: Annotated[int | None, Form()] = None,
    nombre: Annotated[str | None, Form()] = None,
    descripcion: Annotated[str | None, Form()] = None,
    categoria_id: Annotated[UUID | None, Form()] = None,
    negocio_id: Annotated[UUID | None, Form()] = None,
) -> ValeUpdate:
    form = await request.form()
    parsed_values = {
        "total_costo": total_costo,
        "total_puntos": total_puntos,
        "nombre": nombre,
        "descripcion": descripcion,
        "categoria_id": categoria_id,
        "negocio_id": negocio_id,
    }
    changes = {
        field: value
        for field, value in parsed_values.items()
        if field in form
        and (
            field == "descripcion"
            or form.get(field) not in (None, "")
        )
    }
    try:
        return ValeUpdate.model_validate(changes)
    except ValidationError as error:
        raise RequestValidationError(error.errors()) from error


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
    responses=_error_responses(400, 401, 403, 404, 409, 422, 500),
)
async def create_vale(
    data: Annotated[ValeCreate, Depends(_parse_vale_create_form)],
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.CREATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    image: Annotated[
        UploadFile | None,
        File(description="Imagen opcional del vale"),
    ] = None,
) -> ValeResponseAudit:
    return await ValeService.create(
        db_session,
        data,
        actor_id=current_user.id,
        image=image,
        settings=settings,
    )


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
    responses=_error_responses(400, 401, 403, 404, 409, 422, 500),
)
async def update_vale(
    vale_id: UUID,
    data: Annotated[ValeUpdate, Depends(_parse_vale_update_form)],
    current_user: Annotated[
        CurrentUser,
        Depends(require_permission(Module.VALE, Action.UPDATE)),
    ],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    image: Annotated[
        UploadFile | None,
        File(description="Nueva imagen opcional del vale"),
    ] = None,
) -> ValeResponseAudit:
    return await ValeService.update(
        db_session,
        vale_id,
        data,
        actor_id=current_user.id,
        image=image,
        settings=settings,
    )


@router.delete(
    "/{vale_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar vale",
    responses=_error_responses(401, 403, 404, 422, 500),
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
