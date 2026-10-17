from datetime import datetime, timezone
from decimal import ROUND_CEILING, Decimal
from uuid import UUID

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.domains.categoria.models import Categoria
from app.domains.categoria.services import CategoriaService
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.negocio.models import Negocio
from app.domains.negocio.services import NegocioService
from app.domains.vale.models import Vale
from app.domains.vale.schemas import (
    ValeCreate,
    ValeDetailResponseAudit,
    ValeNegocioCategoriaResponse,
    ValePuntosSuggestionResponse,
    ValeUpdate,
)
from app.integrations.cloudinary import CloudinaryService
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class ValeService:
    """Consultas y reglas de negocio del dominio de vales."""

    _MAX_POINTS = 2_147_483_647

    @staticmethod
    def _integrity_exception(error: IntegrityError) -> AppException:
        return AppException(
            "Los datos del vale entran en conflicto con un registro existente.",
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
    async def _commit(cls, db_session: AsyncSession, vale: Vale) -> None:
        await cls._commit_transaction(db_session)
        await db_session.refresh(vale)

    @staticmethod
    async def get(
        db_session: AsyncSession,
        vale_id: UUID,
        *,
        include_deleted: bool = False,
        for_update: bool = False,
    ) -> Vale:
        statement = select(Vale).where(Vale.id == vale_id)
        if not include_deleted:
            statement = statement.where(Vale.is_deleted.is_(False))
        if for_update:
            statement = statement.with_for_update()
        result = await db_session.execute(statement)
        vale = result.scalar_one_or_none()
        if vale is None:
            raise AppException(
                "Vale no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return vale

    @staticmethod
    async def get_detail(
        db_session: AsyncSession,
        vale_id: UUID,
    ) -> ValeDetailResponseAudit:
        result = await db_session.execute(
            select(Vale, Categoria)
            .join(Categoria, Categoria.id == Vale.categoria_id)
            .where(
                Vale.id == vale_id,
                Vale.is_deleted.is_(False),
            )
        )
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Vale no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        vale, categoria = row
        negocio = await NegocioService.get_with_sucursales(
            db_session,
            vale.negocio_id,
        )
        return ValeDetailResponseAudit(
            vale=vale,
            negocio=negocio,
            categoria=categoria,
        )

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
        categoria_id: UUID | None = None,
        negocio_id: UUID | None = None,
        include_deleted: bool = False,
    ) -> PaginatedResponse[ValeNegocioCategoriaResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )
        filters = []
        if not include_deleted:
            filters.append(Vale.is_deleted.is_(False))
        if categoria_id is not None:
            filters.append(Vale.categoria_id == categoria_id)
        if negocio_id is not None:
            filters.append(Vale.negocio_id == negocio_id)

        total_result = await db_session.execute(
            select(func.count()).select_from(Vale).where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(Vale, Negocio, Categoria)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .join(Categoria, Categoria.id == Vale.categoria_id)
            .where(*filters)
            .order_by(Vale.nombre, Vale.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        data = [
            ValeNegocioCategoriaResponse(
                vale=vale,
                negocio=negocio,
                categoria=categoria,
            )
            for vale, negocio, categoria in result.all()
        ]
        return PaginatedResponse[ValeNegocioCategoriaResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=data,
        )

    @classmethod
    async def suggest_points(
        cls,
        db_session: AsyncSession,
        total_costo: Decimal,
    ) -> ValePuntosSuggestionResponse:
        config = await ConfigPuntosService.get_active(db_session)
        assert config is not None
        suggested = int(
            (
                total_costo
                * Decimal(config.costo_vale_puntos)
                / Decimal(config.costo_vale_bolivianos)
            ).to_integral_value(rounding=ROUND_CEILING)
        )
        if suggested <= 0 or suggested > cls._MAX_POINTS:
            raise AppException(
                "Los puntos sugeridos exceden el rango permitido.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"total_costo": "El costo produce una cantidad de puntos no válida."},
            )
        return ValePuntosSuggestionResponse(puntos_sugeridos=suggested)

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: ValeCreate,
        actor_id: UUID,
        image: UploadFile | None = None,
        settings: Settings | None = None,
    ) -> Vale:
        await CategoriaService.get(db_session, data.categoria_id)
        await NegocioService.get(db_session, data.negocio_id)
        now = datetime.now(timezone.utc)
        vale = Vale(
            **data.model_dump(),
            image_url=None,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        new_image_url: str | None = None
        if image is not None:
            if settings is None:
                raise RuntimeError("Settings es obligatorio para subir una imagen.")
            upload_result = await CloudinaryService.upload_image(
                image,
                folder=f"vales/{vale.id}",
                settings=settings,
            )
            new_image_url = upload_result["url"]
            vale.image_url = new_image_url
        db_session.add(vale)
        try:
            await cls._commit_transaction(db_session)
        except Exception:
            if new_image_url is not None:
                await CloudinaryService.safe_delete_image(new_image_url)
            raise
        await db_session.refresh(vale)
        logger.info("Vale creado: vale_id=%s actor_id=%s", vale.id, actor_id)
        return vale

    @classmethod
    async def update(
        cls,
        db_session: AsyncSession,
        vale_id: UUID,
        data: ValeUpdate,
        actor_id: UUID,
        image: UploadFile | None = None,
        settings: Settings | None = None,
    ) -> Vale:
        changes = data.model_dump(exclude_unset=True)
        vale = await cls.get(db_session, vale_id, for_update=True)
        if not changes and image is None:
            return vale
        if "categoria_id" in changes:
            await CategoriaService.get(db_session, changes["categoria_id"])
        if "negocio_id" in changes:
            await NegocioService.get(db_session, changes["negocio_id"])

        previous_image_url = vale.image_url
        new_image_url: str | None = None
        if image is not None:
            if settings is None:
                raise RuntimeError("Settings es obligatorio para subir una imagen.")
            upload_result = await CloudinaryService.upload_image(
                image,
                folder=f"vales/{vale.id}",
                settings=settings,
            )
            new_image_url = upload_result["url"]

        for field_name, value in changes.items():
            setattr(vale, field_name, value)
        if new_image_url is not None:
            vale.image_url = new_image_url
        vale.updated_at = datetime.now(timezone.utc)
        vale.updated_by = actor_id
        try:
            await cls._commit_transaction(db_session)
        except Exception:
            if new_image_url is not None:
                await CloudinaryService.safe_delete_image(new_image_url)
            raise
        await db_session.refresh(vale)
        if (
            new_image_url is not None
            and previous_image_url is not None
            and previous_image_url != new_image_url
        ):
            await CloudinaryService.safe_delete_image(previous_image_url)
        logger.info("Vale actualizado: vale_id=%s actor_id=%s", vale.id, actor_id)
        return vale

    @classmethod
    async def delete(
        cls,
        db_session: AsyncSession,
        vale_id: UUID,
        actor_id: UUID,
    ) -> Vale:
        vale = await cls.get(db_session, vale_id, for_update=True)
        now = datetime.now(timezone.utc)
        vale.is_deleted = True
        vale.deleted_at = now
        vale.deleted_by = actor_id
        vale.updated_at = now
        vale.updated_by = actor_id
        await cls._commit(db_session, vale)
        return vale
