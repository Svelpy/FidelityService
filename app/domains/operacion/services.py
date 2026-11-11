from datetime import datetime, timezone
from decimal import ROUND_FLOOR, Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.logging import get_logger
from app.domains.config_puntos.services import ConfigPuntosService
from app.domains.movimientos_puntos.services import MovimientoPuntosService
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.operacion.schemas import (
    OperacionCancel,
    OperacionCreate,
    OperacionDetailResponse,
    OperacionListResponse,
)
from app.domains.sucursal.models import Sucursal
from app.domains.sucursal.services import SucursalService
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.shared.enums import Role
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class OperacionService:
    """Registro inmutable de compras que acumulan puntos."""

    _MAX_POINTS = 2_147_483_647
    _ROLES_WITH_GLOBAL_OPERATION_VISIBILITY = frozenset(
        {Role.SUPERADMIN, Role.ADMIN, Role.OWNER}
    )
    # La anulación nunca la realiza quien registra compras (CAJERO): así una
    # misma persona no puede asignar y retirar puntos por su cuenta.
    _CANCELLER_ROLES = frozenset({Role.ADMIN, Role.OWNER})

    @staticmethod
    def _integrity_exception(error: IntegrityError) -> AppException:
        constraint_name = getattr(error.orig, "constraint_name", None)
        if constraint_name is None:
            constraint_name = getattr(
                getattr(error.orig, "__cause__", None),
                "constraint_name",
                None,
            )
        logger.warning("Operación rechazada por PostgreSQL: regla=%s", constraint_name)

        # Reglas de PostgreSQL que pueden romperse al registrar una compra,
        # traducidas a: (mensaje, status HTTP, código, details).
        known_constraints = {
            "ck_operacion_emisor_receptor_diferentes": (
                "El emisor y el receptor deben ser usuarios diferentes.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"receptor_id": "El cliente no puede ser el mismo usuario que registra la compra."},
            ),
            "ck_operacion_total_compra_positivo": (
                "El total de la compra debe ser mayor que cero.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"total_compra": "El importe debe ser mayor que cero."},
            ),
            "ck_operacion_total_puntos_positivo": (
                "La compra no alcanza el mínimo necesario para acumular puntos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"total_compra": "El importe genera menos de un punto."},
            ),
            "ck_usuario_puntos_no_negativos": (
                "El saldo de puntos del cliente no puede quedar negativo.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "El saldo resultante sería negativo."},
            ),
            "uq_movimientos_puntos_operacion_id": (
                "Los puntos de esta operación ya fueron registrados.",
                409,
                ErrorCode.CONFLICT,
                {"operacion": "La operación ya tiene un movimiento de puntos asociado."},
            ),
            "uq_movimientos_puntos_movimiento_origen_id": (
                "La operación ya fue anulada.",
                409,
                ErrorCode.CONFLICT,
                {"operacion": "La acumulación de esta operación ya fue revertida."},
            ),
            "ck_operacion_anulacion_consistente": (
                "Los datos de anulación de la operación están incompletos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"motivo": "La anulación requiere fecha, responsable y motivo."},
            ),
        }
        if constraint_name in known_constraints:
            message, status_code, code, details = known_constraints[constraint_name]
            return AppException(message, status_code, code, details)

        return AppException(
            "Los datos de la operación entran en conflicto con un registro existente.",
            409,
            ErrorCode.CONFLICT,
        )

    @classmethod
    async def _commit(cls, db_session: AsyncSession, operation: Operacion) -> None:
        try:
            await db_session.commit()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise
        await db_session.refresh(operation)

    @classmethod
    def _calculate_points(
        cls,
        total: Decimal,
        bolivianos: int,
        puntos_conversion: int,
    ) -> int:
        points = int(
            (
                total
                * Decimal(puntos_conversion)
                / Decimal(bolivianos)
            ).to_integral_value(rounding=ROUND_FLOOR)
        )
        if points <= 0:
            raise AppException(
                "La compra no alcanza el mínimo necesario para acumular puntos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"total_compra": "El importe genera menos de un punto."},
            )
        if points > cls._MAX_POINTS:
            raise AppException(
                "Los puntos calculados exceden el máximo permitido.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"total_compra": "El importe genera demasiados puntos."},
            )
        return points

    @classmethod
    def _visibility_filters(
        cls,
        actor_id: UUID,
        actor_role: Role,
    ) -> list[object]:
        """Operaciones que el actor puede ver.

        - Roles globales: todas las operaciones.
        - Cajero: solo las operaciones que él mismo emitió.
        - Cualquier otro rol: ninguna.
        """
        if actor_role in cls._ROLES_WITH_GLOBAL_OPERATION_VISIBILITY:
            return []
        if actor_role is Role.CAJERO:
            return [Operacion.emisor_id == actor_id]
        return [Operacion.id.is_(None)]

    @classmethod
    async def get(
        cls,
        db_session: AsyncSession,
        operation_id: UUID,
        actor_id: UUID,
        actor_role: Role,
    ) -> OperacionDetailResponse:
        operation, recipient, issuer, branch, business = (
            await cls._get_detail_records(
                db_session,
                operation_id,
                actor_id,
                actor_role,
            )
        )
        return OperacionDetailResponse(
            operacion=operation,
            receptor=recipient,
            emisor=issuer,
            sucursal=branch,
            negocio=business,
        )

    @classmethod
    async def get_audit(
        cls,
        db_session: AsyncSession,
        operation_id: UUID,
        actor_id: UUID,
        actor_role: Role,
    ) -> Operacion:
        operation, *_ = await cls._get_detail_records(
            db_session,
            operation_id,
            actor_id,
            actor_role,
            include_deleted=True,
        )
        return operation

    @classmethod
    async def _get_detail_records(
        cls,
        db_session: AsyncSession,
        operation_id: UUID,
        actor_id: UUID,
        actor_role: Role,
        *,
        include_deleted: bool = False,
    ) -> tuple[Operacion, User, User, Sucursal, Negocio]:
        filters = [
            Operacion.id == operation_id,
            *cls._visibility_filters(actor_id, actor_role),
        ]
        if not include_deleted:
            filters.append(Operacion.is_deleted.is_(False))
        receptor = aliased(User)
        emisor = aliased(User)
        result = await db_session.execute(
            select(Operacion, receptor, emisor, Sucursal, Negocio)
            .join(receptor, receptor.id == Operacion.receptor_id)
            .join(emisor, emisor.id == Operacion.emisor_id)
            .join(Sucursal, Sucursal.id == Operacion.sucursal_id)
            .join(Negocio, Negocio.id == Sucursal.negocio_id)
            .where(*filters)
        )
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Operacion no encontrada.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return row

    @classmethod
    async def list(
        cls,
        db_session: AsyncSession,
        actor_id: UUID,
        actor_role: Role,
        *,
        page: int = 1,
        per_page: int = 20,
        emisor_id: UUID | None = None,
        receptor_id: UUID | None = None,
        sucursal_id: UUID | None = None,
        anulada: bool | None = None,
    ) -> PaginatedResponse[OperacionListResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )
        filters = [
            Operacion.is_deleted.is_(False),
            *cls._visibility_filters(actor_id, actor_role),
        ]
        if emisor_id is not None:
            filters.append(Operacion.emisor_id == emisor_id)
        if receptor_id is not None:
            filters.append(Operacion.receptor_id == receptor_id)
        if sucursal_id is not None:
            filters.append(Operacion.sucursal_id == sucursal_id)
        if anulada is True:
            filters.append(Operacion.anulada_at.is_not(None))
        elif anulada is False:
            filters.append(Operacion.anulada_at.is_(None))
        total_result = await db_session.execute(
            select(func.count()).select_from(Operacion).where(*filters)
        )
        total = int(total_result.scalar_one())
        receptor = aliased(User)
        emisor = aliased(User)
        result = await db_session.execute(
            select(Operacion, receptor, emisor, Sucursal)
            .join(receptor, receptor.id == Operacion.receptor_id)
            .join(emisor, emisor.id == Operacion.emisor_id)
            .join(Sucursal, Sucursal.id == Operacion.sucursal_id)
            .where(*filters)
            .order_by(Operacion.created_at.desc(), Operacion.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        data = [
            OperacionListResponse(
                operacion=operation,
                receptor=recipient,
                emisor=issuer,
                sucursal=branch,
            )
            for operation, recipient, issuer, branch in result.all()
        ]
        return PaginatedResponse[OperacionListResponse](
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
        data: OperacionCreate,
        actor_id: UUID,
        sucursal_id: UUID | None,
    ) -> Operacion:
        if sucursal_id is None:
            raise AppException("El emisor debe pertenecer a una sucursal.", 422, ErrorCode.VALIDATION_ERROR)
        if data.receptor_id is not None and data.receptor_id == actor_id:
            raise AppException("El emisor y el receptor deben ser usuarios diferentes.", 422, ErrorCode.VALIDATION_ERROR)

        await SucursalService.get(db_session, sucursal_id)
        if data.receptor_id is not None:
            recipient = await UserService.get(
                db_session,
                data.receptor_id,
                for_update=True,
            )
        else:
            assert data.receptor_data is not None
            recipient = await UserService.register(
                db_session,
                data.receptor_data,
                commit=False,
            )
        if recipient.role is not Role.CLIENTE:
            raise AppException("Los puntos solo pueden asignarse a un cliente.", 422, ErrorCode.VALIDATION_ERROR)

        config = await ConfigPuntosService.get_active(db_session)
        assert config is not None
        total_points = cls._calculate_points(
            data.total_compra,
            config.asignacion_bolivianos,
            config.asignacion_puntos,
        )
        now = datetime.now(timezone.utc)
        operation = Operacion(
            receptor_id=recipient.id,
            emisor_id=actor_id,
            total_compra=data.total_compra,
            total_puntos=total_points,
            config_punto_id=config.id,
            sucursal_id=sucursal_id,
            referencia=data.referencia,
            created_at=now,
            created_by=actor_id,
            updated_at=now,
            updated_by=actor_id,
            is_deleted=False,
        )
        try:
            db_session.add(operation)
            await db_session.flush()
            MovimientoPuntosService.register_accrual(
                db_session,
                recipient,
                total_points,
                operation.id,
                actor_id,
                now,
            )
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise
        await cls._commit(db_session, operation)
        logger.info(
            "Operación creada: operation_id=%s emisor_id=%s receptor_id=%s",
            operation.id,
            actor_id,
            recipient.id,
        )
        return operation

    @classmethod
    async def cancel(
        cls,
        db_session: AsyncSession,
        operation_id: UUID,
        data: OperacionCancel,
        actor_id: UUID,
        actor_role: Role,
    ) -> Operacion:
        """Anula una operación revirtiendo sus puntos en una sola transacción.

        La operación y su ACUMULA no se modifican en sus importes: se marca la
        operación como anulada y se registra un movimiento REVERSA que descuenta
        del cliente los puntos acumulados.
        """
        if actor_role not in cls._CANCELLER_ROLES:
            raise AppException(
                "No tienes permisos para anular operaciones.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )

        try:
            result = await db_session.execute(
                select(Operacion)
                .where(
                    Operacion.id == operation_id,
                    Operacion.is_deleted.is_(False),
                )
                .with_for_update()
            )
            operation = result.scalar_one_or_none()
            if operation is None:
                raise AppException(
                    "Operacion no encontrada.",
                    404,
                    ErrorCode.RESOURCE_NOT_FOUND,
                )
            if operation.anulada_at is not None:
                raise AppException(
                    "La operación ya fue anulada.",
                    409,
                    ErrorCode.CONFLICT,
                    {"anulada_at": operation.anulada_at.isoformat()},
                )

            now = datetime.now(timezone.utc)
            accrual = await MovimientoPuntosService.get_by_operation_id(
                db_session,
                operation.id,
                for_update=True,
            )
            if accrual is None:
                raise AppException(
                    "La operación no tiene un movimiento de acumulación asociado.",
                    409,
                    ErrorCode.CONFLICT,
                )
            recipient = await UserService.get(
                db_session,
                operation.receptor_id,
                include_deleted=True,
                for_update=True,
            )

            MovimientoPuntosService.register_reversal(
                db_session,
                recipient,
                accrual,
                actor_id,
                now,
            )
            operation.anulada_at = now
            operation.anulada_por = actor_id
            operation.motivo_anulacion = data.motivo
            operation.updated_at = now
            operation.updated_by = actor_id
            await db_session.flush()
        except IntegrityError as error:
            await db_session.rollback()
            raise cls._integrity_exception(error) from error
        except Exception:
            await db_session.rollback()
            raise
        await cls._commit(db_session, operation)
        logger.info(
            "Operación anulada: operation_id=%s anulada_por=%s receptor_id=%s puntos=%s",
            operation.id,
            actor_id,
            operation.receptor_id,
            operation.total_puntos,
        )
        return operation
