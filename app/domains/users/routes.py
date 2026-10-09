from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domains.auth.dependencies import (
    get_current_principal,
    require_permission,
)
from app.domains.auth.schemas import CurrentUser
from app.domains.users.schemas import (
    AdminResetPassword,
    PasswordSelfUpdate,
    UserCreate,
    UserResponse,
    UserResponseAudit,
    UserSelfUpdate,
    UserUpdate,
)
from app.domains.users.services import UserService
from app.shared.enums import Action, Module
from app.shared.schemas.errors import ErrorResponse
from app.shared.schemas.pagination import PaginatedResponse


router = APIRouter(prefix="/users", tags=["Users"])

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
    "/me",
    response_model=UserResponse,
    summary="Consultar mi usuario",
    responses=_error_responses(401, 404, 500),
)
async def get_me(
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    return await UserService.get(db_session, current_user.id)


@router.patch(
    "/me/password",
    response_model=UserResponse,
    summary="Cambiar mi contraseña",
    responses=_error_responses(400, 401, 404, 422, 500),
)
async def change_my_password(
    data: PasswordSelfUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    return await UserService.change_password(
        db_session,
        current_user.id,
        data,
        current_user.id,
    )


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Actualizar mi usuario",
    responses=_error_responses(401, 404, 422, 500),
)
async def update_me(
    data: UserSelfUpdate,
    current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    return await UserService.update(
        db_session,
        current_user.id,
        data,
        current_user.id,
    )


@router.get(
    "/",
    response_model=PaginatedResponse[UserResponse],
    summary="Listar usuarios",
    responses=_error_responses(401, 403, 422, 500),
)
async def list_users(
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    per_page: Annotated[int, Query(ge=1, le=100)] = 20,
) -> PaginatedResponse[UserResponse]:
    return await UserService.list(
        db_session,
        page=page,
        per_page=per_page,
    )


@router.post(
    "/",
    response_model=UserResponseAudit,
    status_code=status.HTTP_201_CREATED,
    summary="Crear usuario",
    responses=_error_responses(401, 403, 409, 422, 500),
)
async def create_user(
    data: UserCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.CREATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponseAudit:
    return await UserService.create(
        db_session,
        data,
        actor_id=current_user.id,
    )


@router.patch(
    "/{user_id}/password",
    response_model=UserResponseAudit,
    summary="Restablecer contraseña de usuario",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def reset_user_password(
    user_id: UUID,
    data: AdminResetPassword,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponseAudit:
    return await UserService.reset_password(
        db_session,
        user_id,
        data,
        current_user.id,
    )


@router.get(
    "/{user_id}",
    response_model=UserResponseAudit,
    summary="Consultar usuario",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def get_user(
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.READ))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponseAudit:
    return await UserService.get(db_session, user_id)


@router.patch(
    "/{user_id}",
    response_model=UserResponseAudit,
    summary="Actualizar usuario",
    responses=_error_responses(401, 403, 404, 409, 422, 500),
)
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.UPDATE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponseAudit:
    return await UserService.update(
        db_session,
        user_id,
        data,
        current_user.id,
    )


@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar usuario",
    responses=_error_responses(401, 403, 404, 422, 500),
)
async def delete_user(
    user_id: UUID,
    current_user: Annotated[CurrentUser, Depends(require_permission(Module.USUARIO, Action.DELETE))],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    await UserService.delete(db_session, user_id, current_user.id)
