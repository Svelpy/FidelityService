import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.canje.models import Canje
from app.domains.canje.schemas import CanjeCreate, CanjeExpireResponse, CanjeResponse
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.sucursal.services import SucursalService
from app.domains.users.services import UserService
from app.domains.vale.services import ValeService
from app.shared.enums import EstadoCanje, Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class CanjeService:
    """Ciclo de vida de solicitudes de canje de vales."""

    _ROLES_WITH_GLOBAL_VISIBILITY = frozenset({Role.SUPERADMIN, Role.ADMIN, Role.OWNER})
    _REDEEMER_ROLES = frozenset({Role.CAJERO, Role.SOCIO})
    _CANCELLER_ROLES = frozenset(
        {Role.SUPERADMIN, Role.OWNER, Role.ADMIN, Role.CAJERO, Role.SOCIO}
    )
    _CODE_GENERATION_ATTEMPTS = 10

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
        constraint_name = cls._constraint_name(error)
        if constraint_name == "uq_canje_codigo_canje":
            return AppException(
                "El código de canje fue asignado simultáneamente; "
                "intenta nuevamente.",
                409,
                ErrorCode.CONFLICT,
            )
        if constraint_name == "ck_canje_negocio_compatible":
            return AppException(
                "El vale y la sucursal deben pertenecer al mismo negocio.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )
        return AppException(
            "Los datos del canje entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit(cls, db_session: AsyncSession, redemption: Canje) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise
        await db_session.refresh(redemption)

    @classmethod
    async def _generate_unique_code(cls, db_session: AsyncSession) -> str:
        for _ in range(cls._CODE_GENERATION_ATTEMPTS):
            code = f"{secrets.randbelow(100_000_000):08d}"
            result = await db_session.execute(
                select(Canje.id).where(Canje.codigo_canje == code)
            )
            if result.scalar_one_or_none() is None:
                return code
        raise AppException(
            "No fue posible generar un código de canje único.",
            503,
            ErrorCode.CONFLICT,
        )

    @classmethod
    def _visibility_filters(
        cls,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> list[object]:
        if actor_role in cls._ROLES_WITH_GLOBAL_VISIBILITY:
            return []
        if actor_role is Role.CLIENTE:
            return [Canje.cliente_id == actor_id]
        if actor_role in cls._REDEEMER_ROLES:
            return [Canje.sucursal_id == actor_sucursal_id]
        return [Canje.id.is_(None)]

    @staticmethod
    async def _get_raw(
        db_session: AsyncSession,
        redemption_id: UUID,
        *,
        for_update: bool = False,
    ) -> Canje:
        statement = select(Canje).where(
            Canje.id == redemption_id,
            Canje.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await db_session.execute(statement)
        redemption = result.scalar_one_or_none()
        if redemption is None:
            raise AppException(
                "Canje no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return redemption

    @classmethod
    async def get(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> Canje:
        filters = [
            Canje.id == redemption_id,
            Canje.is_deleted.is_(False),
            *cls._visibility_filters(
                actor_id,
                actor_role,
                actor_sucursal_id,
            ),
        ]
        result = await db_session.execute(select(Canje).where(*filters))
        redemption = result.scalar_one_or_none()
        if redemption is None:
            raise AppException(
                "Canje no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return redemption

    @classmethod
    async def list(
        cls,
        db_session: AsyncSession,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
        *,
        page: int = 1,
        per_page: int = 20,
        cliente_id: UUID | None = None,
        dador_id: UUID | None = None,
        vale_id: UUID | None = None,
        status: EstadoCanje | None = None,
        sucursal_id: UUID | None = None,
    ) -> PaginatedResponse[CanjeResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )
        filters = [
            Canje.is_deleted.is_(False),
            *cls._visibility_filters(
                actor_id,
                actor_role,
                actor_sucursal_id,
            ),
        ]
        if cliente_id is not None:
            filters.append(Canje.cliente_id == cliente_id)
        if dador_id is not None:
            filters.append(Canje.dador_id == dador_id)
        if vale_id is not None:
            filters.append(Canje.vale_id == vale_id)
        if status is not None:
            filters.append(Canje.status == status)
        if sucursal_id is not None:
            filters.append(Canje.sucursal_id == sucursal_id)

        total_result = await db_session.execute(
            select(func.count()).select_from(Canje).where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(Canje)
            .where(*filters)
            .order_by(Canje.created_at.desc(), Canje.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        redemptions = list(result.scalars().all())
        return PaginatedResponse[CanjeResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=redemptions,
        )

    @staticmethod
    async def list_for_user(
        db_session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        per_page: int = 20,
    ) -> PaginatedResponse[CanjeResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginaciÃ³n indicada no es vÃ¡lida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )

        filters = [
            Canje.is_deleted.is_(False),
            or_(Canje.cliente_id == user_id, Canje.dador_id == user_id),
        ]
        total_result = await db_session.execute(
            select(func.count()).select_from(Canje).where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(Canje)
            .where(*filters)
            .order_by(Canje.created_at.desc(), Canje.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        redemptions = list(result.scalars().all())
        return PaginatedResponse[CanjeResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=redemptions,
        )

    @classmethod
    async def create(
        cls,
        db_session: AsyncSession,
        data: CanjeCreate,
        actor_id: UUID,
        actor_role: Role,
    ) -> Canje:
        if actor_role is not Role.CLIENTE:
            raise AppException(
                "Solo un cliente puede solicitar un canje.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )

        voucher = await ValeService.get(db_session, data.vale_id)
        client = await UserService.get(db_session, actor_id, for_update=True)
        if client.puntos < voucher.total_puntos:
            raise AppException(
                "No tienes puntos suficientes para solicitar este canje.",
                409,
                ErrorCode.CONFLICT,
                {"puntos": "El saldo disponible es insuficiente."},
            )

        config = await ConfigPuntosService.get_active(db_session)
        assert config is not None
        code = await cls._generate_unique_code(db_session)
        now = datetime.now(timezone.utc)
        redemption = Canje(
            cliente_id=client.id,
            dador_id=None,
            vale_id=voucher.id,
            status=EstadoCanje.PENDIENTE,
            expires_at=now + timedelta(days=30),
            codigo_canje=code,
            sucursal_id=None,
            total_puntos=voucher.total_puntos,
            total_costo=voucher.total_costo,
            referencia=data.referencia,
            config_punto_id=config.id,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(redemption)
        try:
            await db_session.flush()
            MovimientoPuntosService.register_redemption(
                db_session,
                client,
                redemption.total_puntos,
                redemption.id,
                actor_id,
                now,
            )
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise

        await cls._commit(db_session, redemption)
        logger.info(
            "Canje solicitado y puntos descontados: canje_id=%s cliente_id=%s",
            redemption.id,
            client.id,
        )
        return redemption

    @staticmethod
    async def expire_pending(
        db_session: AsyncSession,
        actor_id: UUID,
    ) -> CanjeExpireResponse:
        now = datetime.now(timezone.utc)
        statement = (
            update(Canje)
            .where(
                Canje.is_deleted.is_(False),
                Canje.status == EstadoCanje.PENDIENTE,
                Canje.expires_at <= now,
            )
            .values(
                status=EstadoCanje.EXPIRADO,
                updated_at=now,
                updated_by=actor_id,
            )
        )
        try:
            result = await db_session.execute(statement)
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        expired_count = max(int(result.rowcount or 0), 0)
        logger.info(
            "Canjes expirados en lote: total=%s actor_id=%s",
            expired_count,
            actor_id,
        )
        return CanjeExpireResponse(expired_count=expired_count)

    @classmethod
    async def redeem(
        cls,
        db_session: AsyncSession,
        code: str,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> Canje:
        if actor_role not in cls._REDEEMER_ROLES or actor_sucursal_id is None:
            raise AppException(
                "Solo un usuario operativo asignado a una sucursal puede canjear.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )

        result = await db_session.execute(
            select(Canje)
            .where(
                Canje.codigo_canje == code,
                Canje.is_deleted.is_(False),
            )
            .with_for_update()
        )
        redemption = result.scalar_one_or_none()
        if redemption is None:
            raise AppException(
                "Código de canje no válido.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        if redemption.status is not EstadoCanje.PENDIENTE:
            raise AppException(
                "El canje ya no se encuentra pendiente.",
                409,
                ErrorCode.CONFLICT,
                {"status": redemption.status.value},
            )

        now = datetime.now(timezone.utc)
        if redemption.expires_at <= now:
            redemption.status = EstadoCanje.EXPIRADO
            redemption.updated_at = now
            redemption.updated_by = actor_id
            await cls._commit(db_session, redemption)
            raise AppException(
                "El código de canje ha expirado.",
                409,
                ErrorCode.CONFLICT,
            )

        branch = await SucursalService.get(db_session, actor_sucursal_id)
        voucher = await ValeService.get(db_session, redemption.vale_id)
        if branch.negocio_id != voucher.negocio_id:
            raise AppException(
                "El vale no puede canjearse en la sucursal del dador.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"sucursal_id": "La sucursal pertenece a otro negocio."},
            )
        redemption.status = EstadoCanje.CANJEADO
        redemption.dador_id = actor_id
        redemption.sucursal_id = branch.id
        redemption.updated_at = now
        redemption.updated_by = actor_id

        await cls._commit(db_session, redemption)
        logger.info(
            "Canje confirmado: canje_id=%s dador_id=%s cliente_id=%s",
            redemption.id,
            actor_id,
            redemption.cliente_id,
        )
        return redemption

    @classmethod
    async def cancel(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
    ) -> Canje:
        if actor_role not in cls._CANCELLER_ROLES:
            raise AppException(
                "No tienes permisos para cancelar este canje.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )
        redemption = await cls._get_raw(
            db_session,
            redemption_id,
            for_update=True,
        )
        if redemption.status is not EstadoCanje.PENDIENTE:
            raise AppException(
                "Solo puede cancelarse un canje pendiente.",
                409,
                ErrorCode.CONFLICT,
                {"status": redemption.status.value},
            )

        now = datetime.now(timezone.utc)
        if redemption.expires_at <= now:
            redemption.status = EstadoCanje.EXPIRADO
            redemption.updated_at = now
            redemption.updated_by = actor_id
            await cls._commit(db_session, redemption)
            raise AppException(
                "El canje ya se encontraba expirado.",
                409,
                ErrorCode.CONFLICT,
            )

        movement = await MovimientoPuntosService.get_by_redemption_id(
            db_session,
            redemption.id,
            for_update=True,
        )
        client = await UserService.get(
            db_session,
            redemption.cliente_id,
            for_update=True,
        )
        try:
            MovimientoPuntosService.register_adjustment(
                db_session,
                client,
                redemption.total_puntos,
                actor_id,
                now,
                movement.id if movement is not None else None,
            )
            redemption.status = EstadoCanje.CANCELADO
            redemption.updated_at = now
            redemption.updated_by = actor_id
        except Exception:
            await db_session.rollback()
            raise

        await cls._commit(db_session, redemption)
        logger.info(
            "Canje cancelado y puntos repuestos: canje_id=%s actor_id=%s",
            redemption.id,
            actor_id,
        )
        return redemption
