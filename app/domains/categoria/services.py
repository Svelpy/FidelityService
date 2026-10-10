from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.categoria.models import Categoria
from app.domains.categoria.schemas import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaUpdate,
)
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse
from app.shared.services.slug import generate_slug


logger = get_logger(__name__)


class CategoriaService:
    """Consultas y reglas de negocio del dominio de categorías."""

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

        if constraint_name == "uq_categoria_slug":
            return AppException(
                "Ya existe una categoría con ese nombre.",
                409,
                ErrorCode.CONFLICT,
                {"nombre": "El nombre genera un slug que ya está registrado."},
            )

        return AppException(
            "Los datos de la categoría entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit(
        cls,
        db_session: AsyncSession,
        categoria: Categoria,
    ) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

        await db_session.refresh(categoria)

    @staticmethod
    async def _validate_unique_slug(
        db_session: AsyncSession,
        slug: str,
        *,
        exclude_categoria_id: UUID | None = None,
    ) -> None:
        statement = select(Categoria.id).where(Categoria.slug == slug)
        if exclude_categoria_id is not None:
            statement = statement.where(Categoria.id != exclude_categoria_id)

        result = await db_session.execute(statement)
        if result.scalar_one_or_none() is not None:
            raise AppException(
                "Ya existe una categoría con ese nombre.",
                409,
                ErrorCode.CONFLICT,
                {"nombre": "El nombre genera un slug que ya está registrado."},
            )

    @staticmethod
    async def get(
        db_session: AsyncSession,
        categoria_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Categoria:
        statement = select(Categoria).where(Categoria.id == categoria_id)
        if not include_deleted:
            statement = statement.where(Categoria.is_deleted.is_(False))
        if for_update:
            statement = statement.with_for_update()

        result = await db_session.execute(statement)
        categoria = result.scalar_one_or_none()
        if categoria is None:
            raise AppException(
                "Categoría no encontrada.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return categoria

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
        include_deleted: bool = False,
    ) -> PaginatedResponse[CategoriaResponse]:
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
            filters.append(Categoria.is_deleted.is_(False))

        total_result = await db_session.execute(
            select(func.count()).select_from(Categoria).where(*filters)
        )
        total = int(total_result.scalar_one())

        result = await db_session.execute(
            select(Categoria)
            .where(*filters)
            .order_by(Categoria.nombre, Categoria.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        categorias = list(result.scalars().all())
        total_pages = (total + per_page - 1) // per_page
        return PaginatedResponse[CategoriaResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=categorias,
        )

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: CategoriaCreate,
        actor_id: UUID,
    ) -> Categoria:
        slug = generate_slug(data.nombre)
        await cls._validate_unique_slug(db_session, slug)

        now = datetime.now(timezone.utc)
        categoria = Categoria(
            **data.model_dump(),
            slug=slug,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(categoria)
        await cls._commit(db_session, categoria)

        logger.info(
            "Categoría creada: categoria_id=%s actor_id=%s",
            categoria.id,
            actor_id,
        )
        return categoria

    @classmethod
    async def update(
        cls,
        db_session: AsyncSession,
        categoria_id: UUID,
        data: CategoriaUpdate,
        actor_id: UUID,
    ) -> Categoria:
        changes = data.model_dump(exclude_unset=True)
        categoria = await cls.get(db_session, categoria_id, for_update=True)
        if not changes:
            return categoria

        if "nombre" in changes:
            slug = generate_slug(changes["nombre"])
            await cls._validate_unique_slug(
                db_session,
                slug,
                exclude_categoria_id=categoria.id,
            )
            changes["slug"] = slug

        for field_name, value in changes.items():
            setattr(categoria, field_name, value)

        categoria.updated_at = datetime.now(timezone.utc)
        categoria.updated_by = actor_id
        await cls._commit(db_session, categoria)

        logger.info(
            "Categoría actualizada: categoria_id=%s actor_id=%s",
            categoria.id,
            actor_id,
        )
        return categoria

    @classmethod
    async def delete(
        cls,
        db_session: AsyncSession,
        categoria_id: UUID,
        actor_id: UUID,
    ) -> Categoria:
        categoria = await cls.get(db_session, categoria_id, for_update=True)
        now = datetime.now(timezone.utc)

        categoria.is_deleted = True
        categoria.deleted_at = now
        categoria.deleted_by = actor_id
        categoria.updated_at = now
        categoria.updated_by = actor_id
        await cls._commit(db_session, categoria)

        logger.info(
            "Categoría eliminada: categoria_id=%s actor_id=%s",
            categoria.id,
            actor_id,
        )
        return categoria
