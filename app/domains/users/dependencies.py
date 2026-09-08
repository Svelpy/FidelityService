from beanie import PydanticObjectId
from fastapi import Depends

from app.core.repositories import BaseRepository, TenantRepository
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.services.permissions import PLATFORM_ROLES
from app.domains.auth.dependencies import get_current_principal
from app.domains.auth.schemas import CurrentUser
from app.domains.users.models import User


def get_global_user_repository() -> BaseRepository[User]:
    """Repositorio global para unicidad y autogestión del usuario."""
    return BaseRepository(User)


async def get_current_tenant_user_repository(current_user: CurrentUser = Depends(get_current_principal)) -> TenantRepository[User]:
    """Repositorio limitado al negocio del usuario autenticado."""
    if current_user.role in PLATFORM_ROLES or current_user.business_id is None:
        raise AppException("El usuario no tiene un negocio tenant autorizado.",403,ErrorCode.PERMISSION_DENIED)

    return TenantRepository(User, current_user.business_id)


async def get_selected_tenant_user_repository(business_id: PydanticObjectId,current_user: CurrentUser = Depends(get_current_principal)) -> TenantRepository[User]:
    """Repositorio del negocio seleccionado por un usuario de plataforma."""
    if current_user.role not in PLATFORM_ROLES:
        raise AppException("Solo los usuarios de plataforma pueden seleccionar un negocio.",403,ErrorCode.PERMISSION_DENIED)

    return TenantRepository(User, business_id)
