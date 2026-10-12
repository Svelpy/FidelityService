from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.schemas import (
    ConfigPuntosCreate,
    ConfigPuntosResponse,
    FactorPuntosInput,
)
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class ConfigPuntosService:
    """Versionado y consulta de los factores globales del sistema."""

    _FACTOR_QUANTUM = Decimal("0.000001")
    _MAX_FACTOR = Decimal("999999999999.999999")

    @staticmethod
    def _constraint_name(error: IntegrityError) -> str | None:
        constraint_name = getattr(error.orig, "constraint_name", None)
        if constraint_name is not None:
            return constraint_name
        return getattr(
            getattr(error.orig, "__cause__", None),
            "constraint_name",
            None,
        )

    @classmethod
    def _integrity_exception(cls, error: IntegrityError) -> AppException:
        if cls._constraint_name(error) == "uq_config_puntos_activa":
            return AppException(
                "La configuración de puntos fue modificada simultáneamente.",
                409,
                ErrorCode.CONFLICT,
                {
                    "config_puntos": (
                        "Ya existe otra configuración activa; intenta nuevamente."
                    )
                },
            )
        return AppException(
            "Los datos de la configuración de puntos no son válidos.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    def _calculate_factor(
        cls,
        values: FactorPuntosInput,
        field_name: str,
    ) -> Decimal:
        raw_factor = Decimal(values.cant_puntos) / Decimal(values.cant_bs)
        if raw_factor > cls._MAX_FACTOR:
            raise AppException(
                "El factor calculado es demasiado grande.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {
                    field_name: (
                        "La división excede el máximo admitido por la base de datos."
                    )
                },
            )
        factor = raw_factor.quantize(cls._FACTOR_QUANTUM, rounding=ROUND_HALF_UP)
        if factor <= 0:
            raise AppException(
                "El factor calculado es demasiado pequeño.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {
                    field_name: (
                        "La división debe producir al menos 0.000001 puntos por Bs."
                    )
                },
            )
        return factor

    @staticmethod
    async def get(
        db_session: AsyncSession,
        config_puntos_id: UUID,
    ) -> ConfigPuntos:
        result = await db_session.execute(
            select(ConfigPuntos).where(
                ConfigPuntos.id == config_puntos_id,
                ConfigPuntos.is_deleted.is_(False),
            )
        )
        config = result.scalar_one_or_none()
        if config is None:
            raise AppException(
                "Configuración de puntos no encontrada.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return config

    @staticmethod
    async def get_active(
        db_session: AsyncSession,
        *,
        for_update: bool = False,
        required: bool = True,
    ) -> ConfigPuntos | None:
        statement = select(ConfigPuntos).where(
            ConfigPuntos.end_date.is_(None),
            ConfigPuntos.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()

        result = await db_session.execute(statement)
        config = result.scalar_one_or_none()
        if config is None and required:
            raise AppException(
                "No existe una configuración de puntos activa.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return config

    @staticmethod
    async def list(
        db_session: AsyncSession,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse[ConfigPuntosResponse]:
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

        filters = [ConfigPuntos.is_deleted.is_(False)]
        total_result = await db_session.execute(
            select(func.count()).select_from(ConfigPuntos).where(*filters)
        )
        total = int(total_result.scalar_one())

        result = await db_session.execute(
            select(ConfigPuntos)
            .where(*filters)
            .order_by(ConfigPuntos.start_date.desc(), ConfigPuntos.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        configurations = list(result.scalars().all())
        total_pages = (total + per_page - 1) // per_page
        return PaginatedResponse[ConfigPuntosResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
            data=configurations,
        )

    @classmethod
    async def replace(
        cls,
        db_session: AsyncSession,
        data: ConfigPuntosCreate,
        actor_id: UUID,
    ) -> ConfigPuntos:
        factor_asignacion = cls._calculate_factor(data.asignacion, "asignacion")
        factor_costo_vale = cls._calculate_factor(data.costo_vale, "costo_vale")
        now = datetime.now(timezone.utc)
        active_config = await cls.get_active(
            db_session,
            for_update=True,
            required=False,
        )

        if active_config is not None:
            active_config.end_date = now
            active_config.updated_at = now
            active_config.updated_by = actor_id

        new_config = ConfigPuntos(
            start_date=now,
            end_date=None,
            factor_asignacion_puntos=factor_asignacion,
            factor_costo_vale=factor_costo_vale,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(new_config)

        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

        await db_session.refresh(new_config)
        logger.info(
            "Configuración de puntos reemplazada: config_puntos_id=%s actor_id=%s",
            new_config.id,
            actor_id,
        )
        return new_config
