from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.logging import get_logger
from app.domains.canje.models import Canje
from app.domains.movimientos_puntos.models import MovimientoPuntos
from app.domains.movimientos_puntos.schemas import (
    MovimientoPuntosDetailResponse,
    MovimientoPuntosListMeResponse,
    MovimientoPuntosListResponse,
)
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.domains.vale.models import Vale
from app.shared.enums import Role, TipoMovimiento
from app.shared.errors.codes import ErrorCode
from app.shared.errors.exceptions import AppException
from app.shared.schemas.pagination import PaginatedResponse


logger = get_logger(__name__)


class MovimientoPuntosService:
    """Cambios de saldo y registro del libro mayor de puntos."""

    _MAX_USER_POINTS = 2_147_483_647
    _ROLES_WITH_GLOBAL_VISIBILITY = frozenset(
        {Role.SUPERADMIN, Role.OWNER, Role.ADMIN}
    )
    _ACTOR_SCOPED_ROLES = frozenset({Role.CAJERO})

    @classmethod
    def _visibility_filters(
        cls,
        actor_id: UUID,
        actor_role: Role,
    ) -> list[object]:
        """Filas de movimientos que el actor puede ver.

        - Roles globales: todos los movimientos.
        - Cajero: solo los movimientos producidos por una acción suya:
          ACUMULA de operaciones que emitió, CANJE de canjes que entregó
          (dador), AJUSTE de canjes que canceló (created_by del ajuste) y
          REVERSA de operaciones que emitió, aunque la anulación la haya
          realizado otro usuario.
        - Cualquier otro rol: ninguno. El cliente consulta los suyos mediante
          list_me (GET /movimientos-puntos/me), que no utiliza este filtro.
        """
        if actor_role in cls._ROLES_WITH_GLOBAL_VISIBILITY:
            return []
        if actor_role in cls._ACTOR_SCOPED_ROLES:
            # Alias propios: get_detail y list ya unen estas tablas en la
            # consulta exterior y no deben correlacionarse con ella.
            own_operation = aliased(Operacion)
            own_redemption = aliased(Canje)
            emitted_operations = select(own_operation.id).where(
                own_operation.emisor_id == actor_id
            )
            delivered_redemptions = select(own_redemption.id).where(
                own_redemption.dador_id == actor_id
            )
            own_accrual = aliased(MovimientoPuntos)
            accruals_of_emitted_operations = select(own_accrual.id).where(
                own_accrual.operacion_id.in_(emitted_operations)
            )
            return [
                or_(
                    MovimientoPuntos.operacion_id.in_(emitted_operations),
                    MovimientoPuntos.canje_id.in_(delivered_redemptions),
                    and_(
                        MovimientoPuntos.tipo_movimiento == TipoMovimiento.AJUSTE,
                        MovimientoPuntos.created_by == actor_id,
                    ),
                    and_(
                        MovimientoPuntos.tipo_movimiento == TipoMovimiento.REVERSA,
                        MovimientoPuntos.movimiento_origen_id.in_(
                            accruals_of_emitted_operations
                        ),
                    ),
                )
            ]
        return [MovimientoPuntos.id.is_(None)]

    @staticmethod
    async def get(
        db_session: AsyncSession,
        movement_id: UUID,
        *,
        include_deleted: bool = False,
    ) -> MovimientoPuntos:
        statement = select(MovimientoPuntos).where(MovimientoPuntos.id == movement_id)
        if not include_deleted:
            statement = statement.where(MovimientoPuntos.is_deleted.is_(False))
        result = await db_session.execute(statement)
        movement = result.scalar_one_or_none()
        if movement is None:
            raise AppException(
                "Movimiento de puntos no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )
        return movement

    @staticmethod
    async def get_by_redemption_id(
        db_session: AsyncSession,
        redemption_id: UUID,
        *,
        for_update: bool = False,
    ) -> MovimientoPuntos | None:
        statement = select(MovimientoPuntos).where(
            MovimientoPuntos.canje_id == redemption_id,
            MovimientoPuntos.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await db_session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_operation_id(
        db_session: AsyncSession,
        operation_id: UUID,
        *,
        for_update: bool = False,
    ) -> MovimientoPuntos | None:
        statement = select(MovimientoPuntos).where(
            MovimientoPuntos.operacion_id == operation_id,
            MovimientoPuntos.is_deleted.is_(False),
        )
        if for_update:
            statement = statement.with_for_update()
        result = await db_session.execute(statement)
        return result.scalar_one_or_none()

    @classmethod
    async def get_detail(
        cls,
        db_session: AsyncSession,
        movement_id: UUID,
        actor_id: UUID,
        actor_role: Role,
    ) -> MovimientoPuntosDetailResponse:
        origin_movement = aliased(MovimientoPuntos)
        redemption_id = func.coalesce(
            MovimientoPuntos.canje_id,
            origin_movement.canje_id,
        )
        branch_id = func.coalesce(Canje.sucursal_id, Operacion.sucursal_id)
        business_id = func.coalesce(Sucursal.negocio_id, Vale.negocio_id)
        filters = [
            MovimientoPuntos.id == movement_id,
            MovimientoPuntos.is_deleted.is_(False),
            *cls._visibility_filters(actor_id, actor_role),
        ]

        statement = (
            select(
                MovimientoPuntos,
                Canje,
                Operacion,
                Sucursal,
                Negocio,
            )
            .select_from(MovimientoPuntos)
            .outerjoin(
                origin_movement,
                MovimientoPuntos.movimiento_origen_id == origin_movement.id,
            )
            .outerjoin(Canje, redemption_id == Canje.id)
            .outerjoin(
                Operacion,
                func.coalesce(
                    MovimientoPuntos.operacion_id,
                    origin_movement.operacion_id,
                )
                == Operacion.id,
            )
            .outerjoin(Sucursal, Sucursal.id == branch_id)
            .outerjoin(Vale, Vale.id == Canje.vale_id)
            .outerjoin(Negocio, Negocio.id == business_id)
            .where(*filters)
        )
        result = await db_session.execute(statement)
        row = result.one_or_none()
        if row is None:
            raise AppException(
                "Movimiento de puntos no encontrado.",
                404,
                ErrorCode.RESOURCE_NOT_FOUND,
            )

        movement, redemption, operation, branch, business = row
        return MovimientoPuntosDetailResponse(
            data=movement,
            canje=redemption,
            operacion=operation,
            sucursal=branch,
            negocio=business,
        )

    @staticmethod
    async def list_me(
        db_session: AsyncSession,
        user_id: UUID,
        *,
        page: int = 1,
        per_page: int = 20,
        movement_type: TipoMovimiento | None = None,
    ) -> PaginatedResponse[MovimientoPuntosListMeResponse]:
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
        origin_movement = aliased(MovimientoPuntos)
        redemption_id = func.coalesce(
            MovimientoPuntos.canje_id,
            origin_movement.canje_id,
        )
        result = await db_session.execute(
            select(MovimientoPuntos, Operacion, Canje, Vale)
            .select_from(MovimientoPuntos)
            .outerjoin(
                origin_movement,
                MovimientoPuntos.movimiento_origen_id == origin_movement.id,
            )
            .outerjoin(
                Operacion,
                func.coalesce(
                    MovimientoPuntos.operacion_id,
                    origin_movement.operacion_id,
                )
                == Operacion.id,
            )
            .outerjoin(Canje, redemption_id == Canje.id)
            .outerjoin(Vale, Vale.id == Canje.vale_id)
            .where(*filters)
            .order_by(MovimientoPuntos.created_at.desc(), MovimientoPuntos.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = [
            MovimientoPuntosListMeResponse(
                movimiento=movement,
                operacion=operation,
                canje=redemption,
                vale=voucher,
            )
            for movement, operation, redemption, voucher in result.all()
        ]
        return PaginatedResponse[MovimientoPuntosListMeResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=items,
        )

    @classmethod
    async def list(
        cls,
        db_session: AsyncSession,
        actor_id: UUID,
        actor_role: Role,
        *,
        page: int = 1,
        per_page: int = 20,
        user_id: UUID | None = None,
        movement_type: TipoMovimiento | None = None,
    ) -> PaginatedResponse[MovimientoPuntosListResponse]:
        if page < 1 or per_page < 1 or per_page > 100:
            raise AppException(
                "La paginación indicada no es válida.",
                422,
                ErrorCode.VALIDATION_ERROR,
            )

        filters = [
            MovimientoPuntos.is_deleted.is_(False),
            *cls._visibility_filters(actor_id, actor_role),
        ]
        if user_id is not None:
            filters.append(MovimientoPuntos.usuario_id == user_id)
        if movement_type is not None:
            filters.append(MovimientoPuntos.tipo_movimiento == movement_type)

        total_result = await db_session.execute(
            select(func.count()).select_from(MovimientoPuntos).where(*filters)
        )
        total = int(total_result.scalar_one())
        origin_movement = aliased(MovimientoPuntos)
        redemption_id = func.coalesce(
            MovimientoPuntos.canje_id,
            origin_movement.canje_id,
        )
        client = aliased(User)
        emitter = aliased(User)
        result = await db_session.execute(
            select(MovimientoPuntos, client, emitter, Operacion, Canje, Vale)
            .select_from(MovimientoPuntos)
            .join(client, client.id == MovimientoPuntos.usuario_id)
            .outerjoin(
                origin_movement,
                MovimientoPuntos.movimiento_origen_id == origin_movement.id,
            )
            .outerjoin(
                Operacion,
                func.coalesce(
                    MovimientoPuntos.operacion_id,
                    origin_movement.operacion_id,
                )
                == Operacion.id,
            )
            .outerjoin(emitter, emitter.id == Operacion.emisor_id)
            .outerjoin(Canje, redemption_id == Canje.id)
            .outerjoin(Vale, Vale.id == Canje.vale_id)
            .where(*filters)
            .order_by(MovimientoPuntos.created_at.desc(), MovimientoPuntos.id)
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
        items = [
            MovimientoPuntosListResponse(
                movimiento=movement,
                cliente=client,
                emisor=emitter,
                operacion=operation,
                canje=redemption,
                vale=voucher,
            )
            for movement, client, emitter, operation, redemption, voucher in result.all()
        ]
        return PaginatedResponse[MovimientoPuntosListResponse](
            total=total,
            page=page,
            per_page=per_page,
            total_pages=(total + per_page - 1) // per_page,
            data=items,
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
            movimiento_origen_id=None,
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
            movimiento_origen_id=None,
            created_at=occurred_at,
            created_by=actor_id,
            updated_at=occurred_at,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(movement)
        return movement

    @classmethod
    def register_adjustment(
        cls,
        db_session: AsyncSession,
        user: User,
        points: int,
        actor_id: UUID,
        occurred_at: datetime,
        movement_origin_id: UUID | None = None,
    ) -> MovimientoPuntos:
        """Registra AJUSTE y repone saldo sin confirmar la transacción."""
        if points <= 0:
            raise AppException(
                "El canje debe contener una cantidad positiva de puntos.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "La cantidad de puntos debe ser mayor que cero."},
            )

        new_balance = user.puntos + points
        if new_balance > cls._MAX_USER_POINTS:
            raise AppException(
                "La reposición excede el saldo máximo permitido.",
                422,
                ErrorCode.VALIDATION_ERROR,
                {"puntos": "La operación excede el saldo máximo permitido."},
            )

        user.puntos = new_balance
        user.updated_at = occurred_at
        user.updated_by = actor_id

        movement = MovimientoPuntos(
            usuario_id=user.id,
            tipo_movimiento=TipoMovimiento.AJUSTE,
            puntos=points,
            operacion_id=None,
            canje_id=None,
            movimiento_origen_id=movement_origin_id,
            created_at=occurred_at,
            created_by=actor_id,
            updated_at=occurred_at,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(movement)
        return movement

    @staticmethod
    def register_reversal(
        db_session: AsyncSession,
        user: User,
        accrual: MovimientoPuntos,
        actor_id: UUID,
        occurred_at: datetime,
    ) -> MovimientoPuntos:
        """Registra REVERSA de una acumulación y descuenta saldo sin confirmar."""
        if accrual.tipo_movimiento is not TipoMovimiento.ACUMULA:
            raise AppException(
                "Solo puede revertirse un movimiento de acumulación.",
                409,
                ErrorCode.CONFLICT,
            )
        if user.puntos < accrual.puntos:
            raise AppException(
                "El cliente ya utilizó parte de los puntos de esta operación.",
                409,
                ErrorCode.CONFLICT,
                {
                    "puntos": (
                        f"Saldo disponible {user.puntos}, se requieren "
                        f"{accrual.puntos} para anular la operación."
                    )
                },
            )

        user.puntos -= accrual.puntos
        user.updated_at = occurred_at
        user.updated_by = actor_id

        movement = MovimientoPuntos(
            usuario_id=user.id,
            tipo_movimiento=TipoMovimiento.REVERSA,
            puntos=accrual.puntos,
            operacion_id=None,
            canje_id=None,
            movimiento_origen_id=accrual.id,
            created_at=occurred_at,
            created_by=actor_id,
            updated_at=occurred_at,
            updated_by=actor_id,
            is_deleted=False,
        )
        db_session.add(movement)
        return movement
