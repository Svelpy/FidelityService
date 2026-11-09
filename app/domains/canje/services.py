import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.logging import get_logger
from app.domains.canje.models import Canje
from app.domains.canje.schemas import (
    CanjeByCodigoResponse,
    CanjeCreate,
    CanjeDetailResponse,
    CanjeExpireResponse,
    CanjeListResponse,
)
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.models import Negocio
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.services import SucursalService
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.domains.vale.models import Vale
from app.domains.vale.services import ValeService
from app.shared.enums import EstadoCanje, Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class CanjeService:
    """Ciclo de vida de solicitudes de canje de vales."""

    _ROLES_WITH_GLOBAL_VISIBILITY = frozenset(
        {Role.SUPERADMIN, Role.ADMIN, Role.OWNER}
    )
    _REDEEMER_ROLES = frozenset({Role.ADMIN, Role.CAJERO, Role.SOCIO})
    _BUSINESS_SCOPED_ROLES = frozenset({Role.CAJERO, Role.SOCIO})
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
        if constraint_name == "ck_canje_estado_final_inmutable":
            return AppException(
                "El canje ya no se encuentra pendiente y no puede modificarse.",
                409,
                ErrorCode.CONFLICT,
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
        *,
        include_redeemed_by_others: bool = False,
    ) -> list[object]:
        """Canjes que el actor puede ver.

        - Roles globales: todos los canjes.
        - Cajero y socio: canjes de vales del negocio de su sucursal en estado
          PENDIENTE, EXPIRADO o CANCELADO (no tienen dador), y los CANJEADO
          solo si él mismo los entregó. Con include_redeemed_by_others ve
          también los CANJEADO por otros usuarios de su negocio; lo usa la
          búsqueda por código, que requiere conocer el código del cliente.
        - Cualquier otro rol: ninguno. El cliente consulta los suyos mediante
          list_for_user (GET /canjes/me), que no utiliza este filtro.
        """
        if actor_role in cls._ROLES_WITH_GLOBAL_VISIBILITY:
            return []
        if actor_role in cls._BUSINESS_SCOPED_ROLES:
            # Alias propio: las consultas ya unen la sucursal donde se canjeó.
            actor_branch = aliased(Sucursal)
            actor_business_id = (
                select(actor_branch.negocio_id)
                .where(actor_branch.id == actor_sucursal_id)
                .scalar_subquery()
            )
            filters: list[object] = [Vale.negocio_id == actor_business_id]
            if not include_redeemed_by_others:
                filters.append(
                    or_(
                        Canje.status != EstadoCanje.CANJEADO,
                        Canje.dador_id == actor_id,
                    )
                )
            return filters
        return [Canje.id.is_(None)]

    @staticmethod
    async def _get_raw(
        db_session: AsyncSession,
        redemption_id: UUID,
        *,
        business_id: UUID | None = None,
        for_update: bool = False,
    ) -> Canje:
        statement = select(Canje).where(
            Canje.id == redemption_id,
            Canje.is_deleted.is_(False),
        )
        if business_id is not None:
            # Alcance por negocio: un canje de otro negocio no se encuentra.
            statement = statement.join(Vale, Vale.id == Canje.vale_id).where(
                Vale.negocio_id == business_id
            )
        if for_update:
            statement = statement.with_for_update(of=Canje)
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
    async def _get_detail_records(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
        *,
        include_deleted: bool = False,
    ) -> tuple[Canje, User, User | None, Vale, Sucursal | None, Negocio]:
        filters = [
            Canje.id == redemption_id,
            *cls._visibility_filters(
                actor_id,
                actor_role,
                actor_sucursal_id,
            ),
        ]
        if not include_deleted:
            filters.append(Canje.is_deleted.is_(False))
        cliente = aliased(User)
        cajero_socio = aliased(User)
        result = await db_session.execute(
            select(Canje, cliente, cajero_socio, Vale, Sucursal, Negocio)
            .join(cliente, cliente.id == Canje.cliente_id)
            .outerjoin(cajero_socio, cajero_socio.id == Canje.dador_id)
            .join(Vale, Vale.id == Canje.vale_id)
            .outerjoin(Sucursal, Sucursal.id == Canje.sucursal_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .where(*filters)
        )
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Canje no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return row

    @classmethod
    async def get(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> CanjeDetailResponse:
        redemption, client, redeemer, voucher, branch, business = (
            await cls._get_detail_records(
                db_session,
                redemption_id,
                actor_id,
                actor_role,
                actor_sucursal_id,
            )
        )
        return CanjeDetailResponse(
            canje=redemption,
            usuario_cliente=client,
            usuario_cajero_socio=redeemer,
            vale=voucher,
            sucursal=branch,
            negocio=business,
        )

    @classmethod
    async def get_audit(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> Canje:
        redemption, *_ = await cls._get_detail_records(
            db_session,
            redemption_id,
            actor_id,
            actor_role,
            actor_sucursal_id,
            include_deleted=True,
        )
        return redemption

    @classmethod
    async def get_by_codigo(
        cls,
        db_session: AsyncSession,
        codigo_canje: str,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> CanjeByCodigoResponse:
        result = await db_session.execute(
            select(Canje, Vale, Negocio, User)
            .join(Vale, Vale.id == Canje.vale_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .join(User, User.id == Canje.cliente_id)
            .where(
                Canje.codigo_canje == codigo_canje,
                Canje.is_deleted.is_(False),
                *cls._visibility_filters(
                    actor_id,
                    actor_role,
                    actor_sucursal_id,
                    include_redeemed_by_others=True,
                ),
            )
        )
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Canje no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        redemption, voucher, business, client = row
        return CanjeByCodigoResponse(
            canje=redemption,
            vale=voucher,
            negocio=business,
            usuario_cliente=client,
        )

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
        negocio_id: UUID | None = None,
    ) -> PaginatedResponse[CanjeListResponse]:
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
        if negocio_id is not None:
            filters.append(Vale.negocio_id == negocio_id)

        total_result = await db_session.execute(
            select(func.count())
            .select_from(Canje)
            .join(Vale, Vale.id == Canje.vale_id)
            .where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(Canje, Vale, Sucursal, Negocio)
            .join(Vale, Vale.id == Canje.vale_id)
            .outerjoin(Sucursal, Sucursal.id == Canje.sucursal_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .where(*filters)
            .order_by(Canje.created_at.desc(), Canje.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        data = [
            CanjeListResponse(
                canje=redemption,
                vale=voucher,
                sucursal=branch,
                negocio=business,
            )
            for redemption, voucher, branch, business in result.all()
        ]
        return PaginatedResponse[CanjeListResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=data,
        )

    @staticmethod
    async def list_for_user(
        db_session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        per_page: int = 20,
        status: EstadoCanje | None = None,
        vale_id: UUID | None = None,
        negocio_id: UUID | None = None,
        sucursal_id: UUID | None = None,
    ) -> PaginatedResponse[CanjeListResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )

        filters = [
            Canje.is_deleted.is_(False),
            or_(Canje.cliente_id == user_id, Canje.dador_id == user_id),
        ]
        if status is not None:
            filters.append(Canje.status == status)
        if vale_id is not None:
            filters.append(Canje.vale_id == vale_id)
        if negocio_id is not None:
            filters.append(Vale.negocio_id == negocio_id)
        if sucursal_id is not None:
            filters.append(Canje.sucursal_id == sucursal_id)

        total_result = await db_session.execute(
            select(func.count())
            .select_from(Canje)
            .join(Vale, Vale.id == Canje.vale_id)
            .where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(Canje, Vale, Sucursal, Negocio)
            .join(Vale, Vale.id == Canje.vale_id)
            .outerjoin(Sucursal, Sucursal.id == Canje.sucursal_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .where(*filters)
            .order_by(Canje.created_at.desc(), Canje.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        data = [
            CanjeListResponse(
                canje=redemption,
                vale=voucher,
                sucursal=branch,
                negocio=business,
            )
            for redemption, voucher, branch, business in result.all()
        ]
        return PaginatedResponse[CanjeListResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=data,
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

        voucher = await ValeService.get(
            db_session,
            data.vale_id,
            for_update=True,
        )
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
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> CanjeByCodigoResponse:
        if actor_role not in cls._REDEEMER_ROLES or actor_sucursal_id is None:
            raise AppException(
                "Solo un usuario operativo asignado a una sucursal puede canjear.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )

        # El alcance se aplica en la propia consulta: un canje de otro negocio
        # responde 404 antes de revelar su estado o de escribir sobre él.
        # Aplica a todo rol que canjea, incluido ADMIN, porque la sucursal del
        # canje debe pertenecer al negocio del vale.
        branch = await SucursalService.get(db_session, actor_sucursal_id)
        result = await db_session.execute(
            select(Canje, Vale, Negocio, User)
            .join(Vale, Vale.id == Canje.vale_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .join(User, User.id == Canje.cliente_id)
            .where(
                Canje.id == redemption_id,
                Canje.is_deleted.is_(False),
                Vale.negocio_id == branch.negocio_id,
            )
            .with_for_update(of=Canje)
        )
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Canje no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        redemption, voucher, business, client = row
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
        return CanjeByCodigoResponse(
            canje=redemption,
            vale=voucher,
            negocio=business,
            usuario_cliente=client,
        )

    @classmethod
    async def cancel(
        cls,
        db_session: AsyncSession,
        redemption_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        actor_sucursal_id: UUID | None,
    ) -> Canje:
        if actor_role not in cls._CANCELLER_ROLES:
            raise AppException(
                "No tienes permisos para cancelar este canje.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )
        business_id: UUID | None = None
        if actor_role in cls._BUSINESS_SCOPED_ROLES:
            if actor_sucursal_id is None:
                raise AppException(
                    "No tienes permisos para cancelar este canje.",
                    403,
                    ErrorCode.PERMISSION_DENIED,
                )
            branch = await SucursalService.get(db_session, actor_sucursal_id)
            business_id = branch.negocio_id

        # El alcance se aplica en la propia consulta: un canje de otro negocio
        # responde 404 antes de revelar su estado o de escribir sobre él.
        redemption = await cls._get_raw(
            db_session,
            redemption_id,
            business_id=business_id,
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
