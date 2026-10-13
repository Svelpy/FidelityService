from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.movimientos_puntos.schemas import MovimientoPuntosResponseAudit
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.shared.enums import Role, TipoMovimiento
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class MovimientoPuntosService:
    """Cambios de saldo y registro del libro mayor de puntos."""

    _MAX_USER_POINTS = 2_147_483_647
    _ROLES_ALLOWED_TO_QUERY_USERS = frozenset(
        {Role.SUPERADMIN, Role.ADMIN, Role.CAJERO, Role.SOCIO}
    )
    @staticmethod
    async def list_for_user(
        db_session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        per_page: int = 20,
        movement_type: TipoMovimiento | None = None,
    ) -> PaginatedResponse[MovimientoPuntosResponseAudit]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )

        filters = [
            MovimientoPuntos.is_deleted.is_(False),
            MovimientoPuntos.usuario_id == user_id,
        ]
        if movement_type is not None:
            filters.append(MovimientoPuntos.tipo_movimiento == movement_type)

        total_result = await db_session.execute(
            select(func.count()).select_from(MovimientoPuntos).where(*filters)
        )
        total = int(total_result.scalar_one())
        result = await db_session.execute(
            select(MovimientoPuntos)
            .where(*filters)
            .order_by(MovimientoPuntos.created_at.desc(), MovimientoPuntos.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        movements = list(result.scalars().all())
        return PaginatedResponse[MovimientoPuntosResponseAudit](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=movements,
        )

    @classmethod
    async def list_by_user_id(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
        actor_role: Role,
        *,
        page: int = 1,
        per_page: int = 20,
        movement_type: TipoMovimiento | None = None,
    ) -> PaginatedResponse[MovimientoPuntosResponseAudit]:
        if actor_role not in cls._ROLES_ALLOWED_TO_QUERY_USERS:
            raise AppException(
                "No tienes permisos para consultar movimientos de otro usuario.",
                403,
                ErrorCode.PERMISSION_DENIED,
            )
        await UserService.get(db_session, user_id)
        return await cls.list_for_user(
            db_session,
            user_id,
            page=page,
            per_page=per_page,
            movement_type=movement_type,
        )

    @classmethod
    def register_accrual(
        cls,
        db_session: AsyncSession,
        user: User,
        points: int,
        operation_id: UUID,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> MovimientoPuntos:
        """Registra ACUMULA sin confirmar la transacción contenedora."""
        if points <= 0:
            raise AppException(
                "La acumulación debe contener una cantidad positiva de puntos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "La cantidad de puntos debe ser mayor que cero."},
            )

        new_balance = user.puntos + points
        if new_balance > cls._MAX_USER_POINTS:
            raise AppException(
                "El saldo resultante excede el máximo permitido.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "La operación excede el saldo máximo permitido."},
            )

        user.puntos = new_balance
        user.updated_at = occurred_at
        user.updated_by = actor_id

        movement = MovimientoPuntos(
            usuario_id=user.id,
            tipo_movimiento=TipoMovimiento.ACUMULA,
            puntos=points,
            operacion_id=operation_id,
            canje_id=None,
            created_at=occurred_at,
            created_by=actor_id,
            updated_at=occurred_at,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(movement)
        return movement

    @staticmethod
    def register_redemption(
        db_session: AsyncSession,
        user: User,
        points: int,
        redemption_id: UUID,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> MovimientoPuntos:
        """Registra CANJE y descuenta saldo sin confirmar la transacción."""
        if points <= 0:
            raise AppException(
                "El canje debe contener una cantidad positiva de puntos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "La cantidad de puntos debe ser mayor que cero."},
            )
        if user.puntos < points:
            raise AppException(
                "El cliente no tiene puntos suficientes para realizar el canje.",
                409,
                ErrorCode.CONFLICT,
                {"puntos": "El saldo disponible es insuficiente."},
            )

        user.puntos -= points
        user.updated_at = occurred_at
        user.updated_by = actor_id

        movement = MovimientoPuntos(
            usuario_id=user.id,
            tipo_movimiento=TipoMovimiento.CANJE,
            puntos=points,
            operacion_id=None,
            canje_id=redemption_id,
            created_at=occurred_at,
            created_by=actor_id,
            updated_at=occurred_at,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(movement)
        return movement
