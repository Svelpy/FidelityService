from collections.abc import Awaitable, Callable
from typing import Annotated

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.domains.auth.schemas import CurrentUser, TokenClaims
from app.domains.auth.services import AuthService
from app.domains.users.models import User
from app.shared.enums import Action, Module, Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.permissions import has_permission


# auto_error=False permite que el header sea opcional (para endpoints públicos)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="api/v1/auth/login",
    auto_error=False,
)


def _get_token_claims(token: str | None, settings: Settings) -> TokenClaims:
    if token is None:
        raise AppException(
            "Token de autenticación requerido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_REQUIRED,
        )

    payload = decode_access_token(token, settings)
    if payload is None:
        raise AppException(
            "Token inválido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_INVALID,
        )

    try:
        return TokenClaims.model_validate(payload)
    except ValidationError as error:
        raise AppException(
            "Token inválido.",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_INVALID,
        ) from error


def _ensure_permission(
    current_user: CurrentUser,
    module: Module,
    action: Action,
) -> None:
    if not has_permission(current_user.role, module, action):
        raise AppException(
            "No tienes permisos para realizar esta acción.",
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PERMISSION_DENIED,
        )


def _ensure_role(
    current_user: CurrentUser,
    allowed_roles: set[Role] | frozenset[Role],
) -> None:
    if current_user.role not in allowed_roles:
        raise AppException(
            "No tienes permisos para realizar esta acción.",
            status.HTTP_403_FORBIDDEN,
            ErrorCode.PERMISSION_DENIED,
        )


async def _load_current_user(
    token: str,
    settings: Settings,
    db_session: AsyncSession,
) -> User:
    claims = _get_token_claims(token, settings)
    result = await db_session.execute(
        select(User).where(
            User.id == claims.sub,
            User.is_deleted.is_(False),
        )
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise AppException(
            "Token inválido",
            status.HTTP_401_UNAUTHORIZED,
            ErrorCode.TOKEN_INVALID,
        )
    AuthService.validate_user_access(user)
    return user


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    return await _load_current_user(token, settings, db_session)


async def get_current_principal(
    user: Annotated[User, Depends(get_current_user)],
) -> CurrentUser:
    return CurrentUser(
        id=user.id,
        role=user.role,
        sucursal_id=user.sucursal_id,
    )


async def get_current_user_optional(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
    settings: Annotated[Settings, Depends(get_settings)],
    db_session: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    if token is None:
        return None
    return await _load_current_user(token, settings, db_session)


async def get_current_principal_optional(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> CurrentUser | None:
    if user is None:
        return None
    return CurrentUser(
        id=user.id,
        role=user.role,
        sucursal_id=user.sucursal_id,
    )


def require_permission(
    module: Module,
    action: Action,
) -> Callable[..., Awaitable[CurrentUser]]:
    async def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    ) -> CurrentUser:
        _ensure_permission(current_user, module, action)
        return current_user

    return dependency


def require_role(
    *allowed_roles: Role,
) -> Callable[..., Awaitable[CurrentUser]]:
    allowed_role_set = frozenset(allowed_roles)

    async def dependency(
        current_user: Annotated[CurrentUser, Depends(get_current_principal)],
    ) -> CurrentUser:
        _ensure_role(current_user, allowed_role_set)
        return current_user

    return dependency
