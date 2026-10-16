from datetime import datetime, timezone
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import and_, func, select, true
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.config import Settings
from app.core.logging import get_logger
from app.domains.negocio.models import Negocio
from app.domains.negocio.schemas import (
    NegocioCreate,
    NegocioSucursalesResponse,
    NegocioSucursalesResponseAudit,
    NegocioUpdate,
)
from app.domains.sucursal.models import Sucursal
from app.integrations.cloudinary import CloudinaryService
from app.shared.enums import TipoNegocio
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class NegocioService:
    """Consultas y reglas de negocio del dominio de negocios."""

    @staticmethod
    async def _validate_unique_name(
        db_session: AsyncSession,
        nombre: str,
        *,
        exclude_negocio_id: UUID | None = None,
    ) -> None:
        statement = (
            select(Negocio.id)
            .where(
                Negocio.is_deleted.is_(False),
                func.lower(Negocio.nombre) == func.lower(nombre),
            )
            .limit(1)
        )

        if exclude_negocio_id is not None:
            statement = statement.where(
                Negocio.id != exclude_negocio_id
            )

        result = await db_session.execute(statement)

        if result.scalar_one_or_none() is not None:
            raise AppException(
                "Ya existe un negocio con ese nombre.",
                409,
                ErrorCode.CONFLICT,
                {
                    "nombre": (
                        "El nombre ya está registrado por un negocio activo."
                    )
                },
            )

    @staticmethod
    async def _validate_single_active_main(
        db_session: AsyncSession,
        *,
        exclude_negocio_id: UUID | None = None,
    ) -> None:
        statement = (
            select(Negocio.id)
            .where(
                Negocio.tipo == TipoNegocio.MAIN,
                Negocio.is_deleted.is_(False),
            )
            .limit(1)
        )

        if exclude_negocio_id is not None:
            statement = statement.where(
                Negocio.id != exclude_negocio_id
            )

        result = await db_session.execute(statement)

        if result.scalar_one_or_none() is not None:
            raise AppException(
                "Ya existe un negocio principal activo.",
                409,
                ErrorCode.CONFLICT,
                {
                    "tipo": (
                        "Solo puede existir un negocio activo de tipo MAIN."
                    )
                },
            )
    @staticmethod
    def _integrity_exception(error: IntegrityError) -> AppException:
        original_error = error.orig
        constraint_name = getattr(
            original_error,
            "constraint_name",
            None,
        )

        if constraint_name is None:
            constraint_name = getattr(
                getattr(original_error, "__cause__", None),
                "constraint_name",
                None,
            )

        if constraint_name == "uq_negocio_nombre_activo_ci":
            return AppException(
                "Ya existe un negocio con ese nombre.",
                409,
                ErrorCode.CONFLICT,
                {
                    "nombre": (
                        "El nombre ya está registrado por un negocio activo."
                    )
                },
            )

        if constraint_name == "uq_negocio_main_activo":
            return AppException(
                "Ya existe un negocio principal activo.",
                409,
                ErrorCode.CONFLICT,
                {
                    "tipo": (
                        "Solo puede existir un negocio activo de tipo MAIN."
                    )
                },
            )

        return AppException(
            "Los datos del negocio entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit_transaction(cls, db_session: AsyncSession) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

    @classmethod
    async def _commit(
        cls,
        db_session: AsyncSession,
        negocio: Negocio,
    ) -> None:
        await cls._commit_transaction(db_session)
        await db_session.refresh(negocio)

    @staticmethod
    async def get(
        db_session: AsyncSession,
        negocio_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Negocio:
        statement = select(Negocio).where(Negocio.id == negocio_id)
        if not include_deleted:
            statement = statement.where(Negocio.is_deleted.is_(False))
        if for_update:
            statement = statement.with_for_update()

        result = await db_session.execute(statement)
        negocio = result.scalar_one_or_none()
        if negocio is None:
            raise AppException(
                "Negocio no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return negocio

    @classmethod
    async def get_with_sucursales(
        cls,
        db_session: AsyncSession,
        negocio_id: UUID,
    ) -> NegocioSucursalesResponseAudit:
        result = await db_session.execute(
            select(Negocio, Sucursal)
            .outerjoin(
                Sucursal,
                and_(
                    Sucursal.negocio_id == Negocio.id,
                    Sucursal.is_deleted.is_(False),
                ),
            )
            .where(
                Negocio.id == negocio_id,
                Negocio.is_deleted.is_(False),
            )
            .order_by(Sucursal.nombre, Sucursal.id)
        )
        rows = result.all()
        if not rows:
            raise AppException(
                "Negocio no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )

        negocio = rows[0][0]
        sucursales = [
            sucursal
            for _, sucursal in rows
            if sucursal is not None
        ]
        return NegocioSucursalesResponseAudit(
            negocio=negocio,
            sucursales=sucursales,
        )

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
        tipo: TipoNegocio | None = None,
        include_deleted: bool = False,
    ) -> PaginatedResponse[NegocioSucursalesResponse]:
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
            filters.append(Negocio.is_deleted.is_(False))
        if tipo is not None:
            filters.append(Negocio.tipo == tipo)

        total_query = (
            select(func.count().label("total"))
            .select_from(Negocio)
            .where(*filters)
            .cte("negocio_total")
        )
        page_query = (
            select(Negocio)
            .where(*filters)
            .order_by(Negocio.nombre, Negocio.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .cte("negocio_page")
        )
        negocio_page = aliased(Negocio, page_query)
        result = await db_session.execute(
            select(total_query.c.total, negocio_page, Sucursal)
            .select_from(total_query)
            .outerjoin(page_query, true())
            .outerjoin(
                Sucursal,
                and_(
                    Sucursal.negocio_id == page_query.c.id,
                    Sucursal.is_deleted.is_(False),
                ),
            )
            .order_by(
                page_query.c.nombre,
                page_query.c.id,
                Sucursal.nombre,
                Sucursal.id,
            )
        )

        total = 0
        data_por_negocio: dict[UUID, NegocioSucursalesResponse] = {}
        for row_total, negocio, sucursal in result.all():
            total = int(row_total)
            if negocio is None:
                continue
            if negocio.id not in data_por_negocio:
                data_por_negocio[negocio.id] = NegocioSucursalesResponse(
                    negocio=negocio,
                    sucursales=[],
                )
            if sucursal is not None:
                data_por_negocio[negocio.id].sucursales.append(sucursal)

        data = list(data_por_negocio.values())
        total_pages = (total + per_page - 1) // per_page
        return PaginatedResponse[NegocioSucursalesResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=data,
        )

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: NegocioCreate,
        actor_id: UUID,
    ) -> Negocio:
        await cls._validate_unique_name(db_session, data.nombre)

        if data.tipo == TipoNegocio.MAIN:
            await cls._validate_single_active_main(db_session)

        now = datetime.now(timezone.utc)
        negocio = Negocio(
            **data.model_dump(),
            image_url=None,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(negocio)
        await cls._commit(db_session, negocio)

        logger.info(
            "Negocio creado: negocio_id=%s actor_id=%s",
            negocio.id,
            actor_id,
        )
        return negocio

    @classmethod
    async def update(
        cls,
        db_session: AsyncSession,
        negocio_id: UUID,
        data: NegocioUpdate,
        actor_id: UUID,
    ) -> Negocio:
        changes = data.model_dump(exclude_unset=True)
        negocio = await cls.get(db_session, negocio_id, for_update=True)
        if not changes:
            return negocio

        if "nombre" in changes:
            await cls._validate_unique_name(
                db_session,
                changes["nombre"],
                exclude_negocio_id=negocio.id,
            )

        if (
            "tipo" in changes
            and changes["tipo"] == TipoNegocio.MAIN
        ):
            await cls._validate_single_active_main(
                db_session,
                exclude_negocio_id=negocio.id,
            )

        for field_name, value in changes.items():
            setattr(negocio, field_name, value)

        negocio.updated_at = datetime.now(timezone.utc)
        negocio.updated_by = actor_id
        await cls._commit(db_session, negocio)

        logger.info(
            "Negocio actualizado: negocio_id=%s actor_id=%s",
            negocio.id,
            actor_id,
        )
        return negocio

    @classmethod
    async def delete(
        cls,
        db_session: AsyncSession,
        negocio_id: UUID,
        actor_id: UUID,
    ) -> Negocio:
        negocio = await cls.get(db_session, negocio_id, for_update=True)
        now = datetime.now(timezone.utc)

        negocio.is_deleted = True
        negocio.deleted_at = now
        negocio.deleted_by = actor_id
        negocio.updated_at = now
        negocio.updated_by = actor_id
        await cls._commit(db_session, negocio)

        logger.info(
            "Negocio eliminado: negocio_id=%s actor_id=%s",
            negocio.id,
            actor_id,
        )
        return negocio

    @classmethod
    async def upload_image(
        cls,
        db_session: AsyncSession,
        negocio_id: UUID,
        file: UploadFile,
        actor_id: UUID,
        settings: Settings,
    ) -> Negocio:
        negocio = await cls.get(db_session, negocio_id, for_update=True)
        previous_image_url = negocio.image_url
        upload_result = await CloudinaryService.upload_image(
            file,
            folder=f"negocios/{negocio.id}",
            settings=settings,
        )
        new_image_url = upload_result["url"]

        negocio.image_url = new_image_url
        negocio.updated_at = datetime.now(timezone.utc)
        negocio.updated_by = actor_id

        try:
            await cls._commit_transaction(db_session)
        except Exception:
            await CloudinaryService.safe_delete_image(new_image_url)
            raise

        await db_session.refresh(negocio)
        if previous_image_url and previous_image_url != new_image_url:
            await CloudinaryService.safe_delete_image(previous_image_url)

        logger.info(
            "Imagen de negocio actualizada: negocio_id=%s actor_id=%s",
            negocio.id,
            actor_id,
        )
        return negocio

    @classmethod
    async def delete_image(
        cls,
        db_session: AsyncSession,
        negocio_id: UUID,
        actor_id: UUID,
    ) -> Negocio:
        negocio = await cls.get(db_session, negocio_id, for_update=True)
        previous_image_url = negocio.image_url
        if previous_image_url is None:
            return negocio

        negocio.image_url = None
        negocio.updated_at = datetime.now(timezone.utc)
        negocio.updated_by = actor_id
        await cls._commit(db_session, negocio)
        await CloudinaryService.safe_delete_image(previous_image_url)

        logger.info(
            "Imagen de negocio eliminada: negocio_id=%s actor_id=%s",
            negocio.id,
            actor_id,
        )
        return negocio
