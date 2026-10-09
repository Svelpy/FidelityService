import asyncio
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password, verify_password
from app.domains.auth.services import AuthService
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.users.schemas import (
    AdminResetPassword,
    PasswordSelfUpdate,
    UserCreate,
    UserResponse,
    UserSelfUpdate,
    UserUpdate,
)
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class UserService:
    """Consultas y reglas de negocio del dominio de usuarios."""

    @staticmethod
    def _integrity_exception(error: IntegrityError) -> AppException:
        original_error = error.orig
        constraint_name = getattr(original_error, "constraint_name", None)
        if constraint_name is None:
            constraint_name = getattr(
                getattr(original_error, "__cause__", None),
                "constraint_name",
                None,
            )

        if constraint_name == "uq_usuario_ci":
            return AppException(
                "La cédula de identidad ya está registrada.",
                409,
                ErrorCode.CONFLICT,
                {"ci": "La cédula de identidad ya está registrada."},
            )

        return AppException(
            "Los datos del usuario entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit(
        cls,
        db_session: AsyncSession,
        user: User | None = None,
    ) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

        if user is not None:
            await db_session.refresh(user)

    @staticmethod
    async def _validate_unique_ci(
        db_session: AsyncSession,
        ci: str,
        exclude_user_id: UUID | None = None,
    ) -> None:
        statement = select(User.id).where(User.ci == ci)
        if exclude_user_id is not None:
            statement = statement.where(User.id != exclude_user_id)

        result = await db_session.execute(statement)
        if result.scalar_one_or_none() is not None:
            raise AppException(
                "La cédula de identidad ya está registrada.",
                409,
                ErrorCode.CONFLICT,
                {"ci": "La cédula de identidad ya está registrada."},
            )

    @staticmethod
    async def _validate_sucursal(
        db_session: AsyncSession,
        sucursal_id: UUID | None,
    ) -> None:
        if sucursal_id is None:
            return

        result = await db_session.execute(
            select(Sucursal.id).where(
                Sucursal.id == sucursal_id,
                Sucursal.is_deleted.is_(False),
            )
        )
        if result.scalar_one_or_none() is None:
            raise AppException(
                "La sucursal indicada no existe o no está disponible.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"sucursal_id": "La sucursal no está disponible."},
            )

    @staticmethod
    async def get(
        db_session: AsyncSession,
        user_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> User:
        statement = select(User).where(User.id == user_id)
        if not include_deleted:
            statement = statement.where(User.is_deleted.is_(False))
        if for_update:
            statement = statement.with_for_update()

        result = await db_session.execute(statement)
        user = result.scalar_one_or_none()
        if user is None:
            raise AppException(
                "Usuario no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return user

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
        include_deleted: bool = False,
    ) -> PaginatedResponse[UserResponse]:
        if page < 1:
            raise AppException(
                "La página debe ser mayor o igual a 1.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )
        if per_page < 1 or per_page > 100:
            raise AppException(
                "La cantidad por página debe estar entre 1 y 100.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )

        filters = []
        if not include_deleted:
            filters.append(User.is_deleted.is_(False))

        total_result = await db_session.execute(
            select(func.count()).select_from(User).where(*filters)
        )
        total = int(total_result.scalar_one())

        result = await db_session.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        users = list(result.scalars().all())
        total_pages = (total + per_page - 1) // per_page
        return PaginatedResponse[UserResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=users,
        )

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: UserCreate,
        actor_id: UUID | None = None,
    ) -> User:
        await cls._validate_unique_ci(db_session, data.ci)
        await cls._validate_sucursal(db_session, data.sucursal_id)

        now = datetime.now(timezone.utc)
        password_hash = await asyncio.to_thread(hash_password, data.telefono)
        user = User(
            **data.model_dump(),
            password_hash=password_hash,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(user)
        await cls._commit(db_session, user)

        logger.info("Usuario creado: user_id=%s actor_id=%s", user.id, actor_id)
        return user

    @classmethod
    async def update(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
        data: UserUpdate | UserSelfUpdate,
        actor_id: UUID,
    ) -> User:
        changes = data.model_dump(exclude_unset=True)
        if not changes:
            return await cls.get(db_session, user_id)

        user = await cls.get(db_session, user_id, for_update=True)

        if "ci" in changes:
            await cls._validate_unique_ci(
                db_session,
                changes["ci"],
                exclude_user_id=user.id,
            )
        if "sucursal_id" in changes:
            await cls._validate_sucursal(db_session, changes["sucursal_id"])

        for field_name, value in changes.items():
            setattr(user, field_name, value)

        user.updated_at = datetime.now(timezone.utc)
        user.updated_by = actor_id
        await cls._commit(db_session, user)

        logger.info("Usuario actualizado: user_id=%s actor_id=%s", user.id, actor_id)
        return user

    @classmethod
    async def delete(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
        actor_id: UUID,
    ) -> User:
        user = await cls.get(db_session, user_id, for_update=True)
        now = datetime.now(timezone.utc)

        user.is_deleted = True
        user.deleted_at = now
        user.deleted_by = actor_id
        user.updated_at = now
        user.updated_by = actor_id

        await AuthService.revoke_for_user(
            db_session,
            user.id,
            "user_deleted",
        )
        await cls._commit(db_session, user)

        logger.info("Usuario eliminado: user_id=%s actor_id=%s", user.id, actor_id)
        return user

    @classmethod
    async def change_password(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
        data: PasswordSelfUpdate,
        actor_id: UUID,
    ) -> User:
        user = await cls.get(db_session, user_id, for_update=True)
        current_password_is_valid = await asyncio.to_thread(
            verify_password,
            data.current_password,
            user.password_hash,
        )
        if not current_password_is_valid:
            raise AppException(
                "La contraseña actual no es correcta.",
                400,
                ErrorCode.AUTHENTICATION_FAILED,
                {"current_password": "La contraseña actual no es correcta."},
            )

        if data.new_password == data.current_password:
            raise AppException(
                "La nueva contraseña debe ser diferente de la actual.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"new_password": "Debe ser diferente de la contraseña actual."},
            )

        user.password_hash = await asyncio.to_thread(
            hash_password,
            data.new_password,
        )
        user.updated_at = datetime.now(timezone.utc)
        user.updated_by = actor_id

        await AuthService.revoke_for_user(
            db_session,
            user.id,
            "password_changed",
        )
        await cls._commit(db_session, user)

        logger.info(
            "Contraseña cambiada: user_id=%s actor_id=%s",
            user.id,
            actor_id,
        )
        return user

    @classmethod
    async def reset_password(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
        data: AdminResetPassword,
        actor_id: UUID,
    ) -> User:
        user = await cls.get(db_session, user_id, for_update=True)
        password_is_unchanged = await asyncio.to_thread(
            verify_password,
            data.new_password,
            user.password_hash,
        )
        if password_is_unchanged:
            raise AppException(
                "La nueva contraseña debe ser diferente de la actual.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"new_password": "Debe ser diferente de la contraseña actual."},
            )

        user.password_hash = await asyncio.to_thread(
            hash_password,
            data.new_password,
        )
        user.updated_at = datetime.now(timezone.utc)
        user.updated_by = actor_id

        await AuthService.revoke_for_user(
            db_session,
            user.id,
            "admin_password_reset",
        )
        await cls._commit(db_session, user)

        logger.info(
            "Contraseña restablecida: user_id=%s actor_id=%s",
            user.id,
            actor_id,
        )
        return user
