from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.negocio.services import NegocioService
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.schemas import (
    SucursalCreate,
    SucursalResponse,
    SucursalUpdate,
)
from app.domains.users.models import User
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class SucursalService:
    """Consultas y reglas de negocio del dominio de sucursales."""

    @staticmethod
    def _integrity_exception(error: IntegrityError) -> AppException:
        return AppException(
            "Los datos de la sucursal entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit(
        cls,
        db_session: AsyncSession,
        sucursal: Sucursal,
    ) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

        await db_session.refresh(sucursal)

    @staticmethod
    async def _validate_without_linked_users(
        db_session: AsyncSession,
        sucursal_id: UUID,
    ) -> None:
        result = await db_session.execute(
            select(User.id).where(User.sucursal_id == sucursal_id).limit(1)
        )
        if result.scalar_one_or_none() is not None:
            raise AppException(
                "No se puede eliminar la sucursal porque tiene usuarios asociados.",
                409,
                ErrorCode.CONFLICT,
                {
                    "sucursal_id": (
                        "La sucursal tiene usuarios activos o históricos asociados."
                    )
                },
            )

    @staticmethod
    async def get(
        db_session: AsyncSession,
        sucursal_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Sucursal:
        statement = select(Sucursal).where(Sucursal.id == sucursal_id)
        if not include_deleted:
            statement = statement.where(Sucursal.is_deleted.is_(False))
        if for_update:
            statement = statement.with_for_update()

        result = await db_session.execute(statement)
        sucursal = result.scalar_one_or_none()
        if sucursal is None:
            raise AppException(
                "Sucursal no encontrada.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return sucursal

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
        negocio_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> PaginatedResponse[SucursalResponse]:
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
            filters.append(Sucursal.is_deleted.is_(False))
        if negocio_id is not None:
            filters.append(Sucursal.negocio_id == negocio_id)

        total_result = await db_session.execute(
            select(func.count()).select_from(Sucursal).where(*filters)
        )
        total = int(total_result.scalar_one())

        result = await db_session.execute(
            select(Sucursal)
            .where(*filters)
            .order_by(Sucursal.nombre, Sucursal.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        sucursales = list(result.scalars().all())
        total_pages = (total + per_page - 1) // per_page
        return PaginatedResponse[SucursalResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=sucursales,
        )

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: SucursalCreate,
        actor_id: UUID,
    ) -> Sucursal:
        await NegocioService.get(db_session, data.negocio_id)

        now = datetime.now(timezone.utc)
        sucursal = Sucursal(
            **data.model_dump(),
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(sucursal)
        await cls._commit(db_session, sucursal)

        logger.info(
            "Sucursal creada: sucursal_id=%s actor_id=%s",
            sucursal.id,
            actor_id,
        )
        return sucursal

    @classmethod
    async def update(
        cls,
        db_session: AsyncSession,
        sucursal_id: UUID,
        data: SucursalUpdate,
        actor_id: UUID,
    ) -> Sucursal:
        changes = data.model_dump(exclude_unset=True)
        sucursal = await cls.get(db_session, sucursal_id, for_update=True)
        if not changes:
            return sucursal

        if "negocio_id" in changes:
            await NegocioService.get(db_session, changes["negocio_id"])

        for field_name, value in changes.items():
            setattr(sucursal, field_name, value)

        sucursal.updated_at = datetime.now(timezone.utc)
        sucursal.updated_by = actor_id
        await cls._commit(db_session, sucursal)

        logger.info(
            "Sucursal actualizada: sucursal_id=%s actor_id=%s",
            sucursal.id,
            actor_id,
        )
        return sucursal

    @classmethod
    async def delete(
        cls,
        db_session: AsyncSession,
        sucursal_id: UUID,
        actor_id: UUID,
    ) -> Sucursal:
        sucursal = await cls.get(db_session, sucursal_id, for_update=True)
        await cls._validate_without_linked_users(db_session, sucursal.id)
        now = datetime.now(timezone.utc)

        sucursal.is_deleted = True
        sucursal.deleted_at = now
        sucursal.deleted_by = actor_id
        sucursal.updated_at = now
        sucursal.updated_by = actor_id
        await cls._commit(db_session, sucursal)

        logger.info(
            "Sucursal eliminada: sucursal_id=%s actor_id=%s",
            sucursal.id,
            actor_id,
        )
        return sucursal
