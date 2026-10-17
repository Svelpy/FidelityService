from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.logging import get_logger
from app.domains.canje.models import Canje
from app.domains.negocio.models import Negocio
from app.domains.operacion.models import Operacion
from app.domains.resumen.schemas import (
    NivelClienteResponse,
    ResumenAdminResponse,
    ResumenCajeroResponse,
    ResumenCanjesCantidadResponse,
    ResumenCanjesResponse,
    ResumenClienteResponse,
    ResumenClientesResponse,
    ResumenOperacionesPeriodoResponse,
    ResumenOperacionesResponse,
    ResumenTopValeResponse,
)
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.domains.vale.models import Vale
from app.shared.enums import EstadoCanje, NivelCliente, Role


logger = get_logger(__name__)


class ResumenService:
    """Resúmenes de la página de inicio según el tipo de usuario."""

    _NIVELES: tuple[tuple[NivelCliente, int, int | None], ...] = (
        (NivelCliente.BRONCE, 0, 500),
        (NivelCliente.PLATA, 501, 1000),
        (NivelCliente.ORO, 1001, 5000),
        (NivelCliente.DIAMANTE, 5001, None),
    )
    _TOP_VALES_LIMIT = 5

    @classmethod
    def calcular_nivel(cls, puntos: int) -> NivelClienteResponse:
        for index, (nivel, puntos_min, puntos_max) in enumerate(cls._NIVELES):
            if puntos_max is not None and puntos > puntos_max:
                continue
            if puntos_max is None:
                return NivelClienteResponse(
                    actual=nivel,
                    puntos_min=puntos_min,
                    puntos_max=None,
                    siguiente=None,
                    puntos_para_siguiente=None,
                    progreso=100,
                )
            siguiente, siguiente_min, _ = cls._NIVELES[index + 1]
            avance = max(puntos - puntos_min, 0)
            return NivelClienteResponse(
                actual=nivel,
                puntos_min=puntos_min,
                puntos_max=puntos_max,
                siguiente=siguiente,
                puntos_para_siguiente=siguiente_min - puntos,
                progreso=avance * 100 // (siguiente_min - puntos_min),
            )
        raise RuntimeError("La tabla de niveles debe terminar en un nivel abierto.")

    @staticmethod
    def _inicio_periodos(
        offset_hours: int,
        ahora: datetime | None = None,
    ) -> tuple[date, datetime, datetime]:
        zona = timezone(timedelta(hours=offset_hours))
        ahora_local = (ahora or datetime.now(timezone.utc)).astimezone(zona)
        inicio_hoy = ahora_local.replace(hour=0, minute=0, second=0, microsecond=0)
        inicio_mes = inicio_hoy.replace(day=1)
        return inicio_hoy.date(), inicio_hoy, inicio_mes

    @staticmethod
    def _operaciones(
        cantidad: int | None,
        total_compra: Decimal | None,
        puntos_otorgados: int | None,
    ) -> ResumenOperacionesResponse:
        return ResumenOperacionesResponse(
            cantidad=int(cantidad or 0),
            total_compra=total_compra or Decimal("0.00"),
            puntos_otorgados=int(puntos_otorgados or 0),
        )

    @classmethod
    async def get_cliente(
        cls,
        db_session: AsyncSession,
        user_id: UUID,
    ) -> ResumenClienteResponse:
        user = await UserService.get(db_session, user_id)
        return ResumenClienteResponse(
            nombre=user.nombre,
            puntos=user.puntos,
            nivel=cls.calcular_nivel(user.puntos),
        )

    @classmethod
    async def get_admin(
        cls,
        db_session: AsyncSession,
        settings: Settings,
    ) -> ResumenAdminResponse:
        ahora = datetime.now(timezone.utc)
        hoy, inicio_hoy, inicio_mes = cls._inicio_periodos(
            settings.TIMEZONE_OFFSET_HOURS,
            ahora,
        )

        clientes_result = await db_session.execute(
            select(
                func.count(),
                func.count().filter(User.created_at >= inicio_mes),
                func.coalesce(func.sum(User.puntos), 0),
            ).where(
                User.role == Role.CLIENTE,
                User.is_deleted.is_(False),
            )
        )
        total_clientes, nuevos_mes, puntos_en_circulacion = clientes_result.one()

        es_hoy = Operacion.created_at >= inicio_hoy
        operaciones_result = await db_session.execute(
            select(
                func.count().filter(es_hoy),
                func.sum(Operacion.total_compra).filter(es_hoy),
                func.sum(Operacion.total_puntos).filter(es_hoy),
                func.count(),
                func.sum(Operacion.total_compra),
                func.sum(Operacion.total_puntos),
            ).where(
                Operacion.is_deleted.is_(False),
                Operacion.created_at >= inicio_mes,
            )
        )
        operaciones_row = operaciones_result.one()

        canjeado_hoy = (Canje.status == EstadoCanje.CANJEADO) & (
            Canje.updated_at >= inicio_hoy
        )
        canjeado_mes = (Canje.status == EstadoCanje.CANJEADO) & (
            Canje.updated_at >= inicio_mes
        )
        canjes_result = await db_session.execute(
            select(
                func.count().filter(
                    Canje.status == EstadoCanje.PENDIENTE,
                    Canje.expires_at > ahora,
                ),
                func.count().filter(canjeado_hoy),
                func.sum(Canje.total_puntos).filter(canjeado_hoy),
                func.count().filter(canjeado_mes),
                func.sum(Canje.total_puntos).filter(canjeado_mes),
            ).where(Canje.is_deleted.is_(False))
        )
        (
            pendientes,
            canjes_hoy,
            puntos_canjes_hoy,
            canjes_mes,
            puntos_canjes_mes,
        ) = canjes_result.one()

        total_canjes = func.count(Canje.id).label("canjes")
        top_result = await db_session.execute(
            select(Vale.id, Vale.nombre, Negocio.nombre, total_canjes)
            .select_from(Canje)
            .join(Vale, Vale.id == Canje.vale_id)
            .join(Negocio, Negocio.id == Vale.negocio_id)
            .where(
                Canje.is_deleted.is_(False),
                Canje.status == EstadoCanje.CANJEADO,
                Canje.updated_at >= inicio_mes,
            )
            .group_by(Vale.id, Vale.nombre, Negocio.nombre)
            .order_by(total_canjes.desc(), Vale.nombre)
            .limit(cls._TOP_VALES_LIMIT)
        )

        return ResumenAdminResponse(
            fecha=hoy,
            clientes=ResumenClientesResponse(
                total=int(total_clientes or 0),
                nuevos_mes=int(nuevos_mes or 0),
                puntos_en_circulacion=int(puntos_en_circulacion or 0),
            ),
            operaciones=ResumenOperacionesPeriodoResponse(
                hoy=cls._operaciones(*operaciones_row[:3]),
                mes=cls._operaciones(*operaciones_row[3:]),
            ),
            canjes=ResumenCanjesResponse(
                pendientes=int(pendientes or 0),
                hoy=ResumenCanjesCantidadResponse(
                    cantidad=int(canjes_hoy or 0),
                    puntos=int(puntos_canjes_hoy or 0),
                ),
                mes=ResumenCanjesCantidadResponse(
                    cantidad=int(canjes_mes or 0),
                    puntos=int(puntos_canjes_mes or 0),
                ),
            ),
            top_vales_mes=[
                ResumenTopValeResponse(
                    vale_id=vale_id,
                    nombre=nombre,
                    negocio=negocio,
                    canjes=int(canjes),
                )
                for vale_id, nombre, negocio, canjes in top_result.all()
            ],
        )

    @classmethod
    async def get_cajero(
        cls,
        db_session: AsyncSession,
        actor_id: UUID,
        settings: Settings,
    ) -> ResumenCajeroResponse:
        hoy, inicio_hoy, _ = cls._inicio_periodos(settings.TIMEZONE_OFFSET_HOURS)
        result = await db_session.execute(
            select(
                func.count(),
                func.sum(Operacion.total_compra),
                func.sum(Operacion.total_puntos),
            ).where(
                Operacion.is_deleted.is_(False),
                Operacion.emisor_id == actor_id,
                Operacion.created_at >= inicio_hoy,
            )
        )
        return ResumenCajeroResponse(
            fecha=hoy,
            operaciones_hoy=cls._operaciones(*result.one()),
        )
