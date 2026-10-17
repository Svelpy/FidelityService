from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.domains.resumen.services import ResumenService
from app.domains.users.models import User
from app.domains.users.services import UserService
from app.shared.enums import Genero, NivelCliente, Role


def _client(*, points: int) -> User:
    return User(
        nombre="Ana",
        ci="12345678",
        telefono="71234567",
        role=Role.CLIENTE,
        genero=Genero.F,
        puntos=points,
        password_hash="hash",
    )


@pytest.mark.parametrize(
    ("puntos", "nivel"),
    [
        (0, NivelCliente.BRONCE),
        (500, NivelCliente.BRONCE),
        (501, NivelCliente.PLATA),
        (1000, NivelCliente.PLATA),
        (1001, NivelCliente.ORO),
        (5000, NivelCliente.ORO),
        (5001, NivelCliente.DIAMANTE),
        (2_147_483_647, NivelCliente.DIAMANTE),
    ],
)
def test_calcular_nivel_respeta_bordes(puntos: int, nivel: NivelCliente) -> None:
    assert ResumenService.calcular_nivel(puntos).actual is nivel


def test_calcular_nivel_desde_cero() -> None:
    nivel = ResumenService.calcular_nivel(0)

    assert nivel.puntos_min == 0
    assert nivel.puntos_max == 500
    assert nivel.siguiente is NivelCliente.PLATA
    assert nivel.puntos_para_siguiente == 501
    assert nivel.progreso == 0


def test_calcular_nivel_calcula_progreso_dentro_del_nivel() -> None:
    nivel = ResumenService.calcular_nivel(750)

    assert nivel.actual is NivelCliente.PLATA
    assert nivel.siguiente is NivelCliente.ORO
    assert nivel.puntos_para_siguiente == 251
    assert nivel.progreso == 49


def test_calcular_nivel_diamante_no_tiene_siguiente() -> None:
    nivel = ResumenService.calcular_nivel(8000)

    assert nivel.puntos_min == 5001
    assert nivel.puntos_max is None
    assert nivel.siguiente is None
    assert nivel.puntos_para_siguiente is None
    assert nivel.progreso == 100


@pytest.mark.asyncio
async def test_get_cliente_usa_saldo_disponible_del_usuario() -> None:
    client = _client(points=1200)
    session = MagicMock()
    with patch.object(
        UserService,
        "get",
        new=AsyncMock(return_value=client),
    ) as get_user:
        resumen = await ResumenService.get_cliente(session, client.id)

    get_user.assert_awaited_once_with(session, client.id)
    assert resumen.nombre == "Ana"
    assert resumen.puntos == 1200
    assert resumen.nivel.actual is NivelCliente.ORO
    assert resumen.nivel.puntos_para_siguiente == 3801


def _settings() -> MagicMock:
    settings = MagicMock(spec=Settings)
    settings.TIMEZONE_OFFSET_HOURS = -4
    return settings


def _result(*, one: tuple | None = None, rows: list | None = None) -> MagicMock:
    result = MagicMock()
    result.one.return_value = one
    result.all.return_value = rows or []
    return result


def _sql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect()))


def test_inicio_periodos_usa_hora_de_bolivia() -> None:
    ahora = datetime(2026, 10, 17, 2, 0, tzinfo=timezone.utc)

    hoy, inicio_hoy, inicio_mes = ResumenService._inicio_periodos(-4, ahora)

    assert hoy == date(2026, 10, 16)
    assert inicio_hoy == datetime(2026, 10, 16, 4, 0, tzinfo=timezone.utc)
    assert inicio_mes == datetime(2026, 10, 1, 4, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_get_admin_arma_resumen_global() -> None:
    vale_id = uuid4()
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(one=(820, 37, 152300)),
            _result(one=(12, Decimal("1450.50"), 145, 310, Decimal("38420.00"), 3842)),
            _result(one=(18, 4, 2000, 95, 47500)),
            _result(rows=[(vale_id, "Vale Bs 50", "Café Central", 27)]),
        ]
    )

    resumen = await ResumenService.get_admin(session, _settings())

    assert resumen.clientes.total == 820
    assert resumen.clientes.nuevos_mes == 37
    assert resumen.clientes.puntos_en_circulacion == 152300
    assert resumen.operaciones.hoy.cantidad == 12
    assert resumen.operaciones.hoy.total_compra == Decimal("1450.50")
    assert resumen.operaciones.mes.puntos_otorgados == 3842
    assert resumen.canjes.pendientes == 18
    assert resumen.canjes.hoy.puntos == 2000
    assert resumen.canjes.mes.cantidad == 95
    assert resumen.top_vales_mes[0].vale_id == vale_id
    assert resumen.top_vales_mes[0].negocio == "Café Central"

    sqls = [_sql(call.args[0]) for call in session.execute.await_args_list]
    assert "FILTER (WHERE" in sqls[1]
    assert "usuario.role" in sqls[0]
    assert "GROUP BY public.vale.id" in sqls[3]
    assert "LIMIT" in sqls[3]


@pytest.mark.asyncio
async def test_get_admin_convierte_sumas_vacias_en_cero() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _result(one=(0, 0, 0)),
            _result(one=(0, None, None, 0, None, None)),
            _result(one=(0, 0, None, 0, None)),
            _result(rows=[]),
        ]
    )

    resumen = await ResumenService.get_admin(session, _settings())

    assert resumen.operaciones.hoy.total_compra == Decimal("0.00")
    assert resumen.operaciones.mes.puntos_otorgados == 0
    assert resumen.canjes.hoy.puntos == 0
    assert resumen.canjes.mes.puntos == 0
    assert resumen.top_vales_mes == []


@pytest.mark.asyncio
async def test_get_cajero_solo_cuenta_sus_operaciones_de_hoy() -> None:
    actor_id = uuid4()
    session = MagicMock()
    session.execute = AsyncMock(
        return_value=_result(one=(3, Decimal("250.00"), 25)),
    )

    resumen = await ResumenService.get_cajero(session, actor_id, _settings())

    assert resumen.operaciones_hoy.cantidad == 3
    assert resumen.operaciones_hoy.total_compra == Decimal("250.00")
    assert resumen.operaciones_hoy.puntos_otorgados == 25
    statement = session.execute.await_args.args[0]
    assert "operacion.emisor_id" in _sql(statement)
    assert actor_id in statement.compile().params.values()
