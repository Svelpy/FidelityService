from datetime import date, datetime, timezone
from decimal import Decimal
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock

import pytest
from openpyxl import load_workbook
from sqlalchemy.dialects import postgresql

from app.core.config import Settings
from app.domains.negocio.models import Negocio
from app.domains.reportes.schemas import ReportePuntosQuery, ReporteTotales
from app.domains.reportes.services import ReporteService
from app.domains.sucursal.models import Sucursal
from app.domains.users.models import User
from app.shared.enums import Genero, Role, TipoNegocio, TipoReportePuntos


def _query(tipo: TipoReportePuntos = TipoReportePuntos.ASIGNADOS) -> ReportePuntosQuery:
    return ReportePuntosQuery(
        fecha_inicio=date(2026, 11, 1),
        fecha_fin=date(2026, 11, 3),
        tipo=tipo,
    )


def _settings() -> Settings:
    settings = MagicMock(spec=Settings)
    settings.TIMEZONE_OFFSET_HOURS = -4
    return settings


def _user(**overrides: object) -> User:
    values: dict[str, object] = {
        "nombre": "Ana",
        "apellidos": None,
        "ci": "12345678",
        "telefono": "71234567",
        "role": Role.CAJERO,
        "genero": Genero.F,
        "password_hash": "hash",
    }
    values.update(overrides)
    return User(**values)


def _rows(rows: list[tuple[object, ...]]) -> MagicMock:
    result = MagicMock()
    result.all.return_value = rows
    return result


def _scalars(items: list[object]) -> MagicMock:
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def test_rango_utc_usa_dias_locales_completos() -> None:
    inicio, fin = ReporteService._rango_utc(_query(), -4)

    assert inicio.astimezone(timezone.utc) == datetime(2026, 11, 1, 4, tzinfo=timezone.utc)
    assert fin.astimezone(timezone.utc) == datetime(2026, 11, 4, 4, tzinfo=timezone.utc)


def test_dia_local_desplaza_desde_utc() -> None:
    expression = ReporteService._dia_local(Sucursal.created_at, -4)
    sql = str(expression.compile(dialect=postgresql.dialect()))

    assert "timezone(" in sql
    assert "AS DATE" in sql


def test_fuente_canjeados_solo_cuenta_canjes_canjeados() -> None:
    fuente = ReporteService._fuente(TipoReportePuntos.CANJEADOS)
    sql = " ".join(
        str(
            condition.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        )
        for condition in fuente.filtros
    )

    assert "CANJEADO" in sql
    assert fuente.fecha.key == "updated_at"


@pytest.mark.parametrize(
    ("tipo", "roles"),
    [
        (TipoReportePuntos.ASIGNADOS, {Role.ADMIN, Role.CAJERO}),
        (TipoReportePuntos.CANJEADOS, {Role.ADMIN, Role.CAJERO, Role.SOCIO}),
    ],
)
def test_roles_elegibles_por_tipo(tipo: TipoReportePuntos, roles: set[Role]) -> None:
    assert ReporteService._ROLES_ELEGIBLES[tipo] == roles


@pytest.mark.parametrize(
    ("tipo", "tipos_negocio"),
    [
        (TipoReportePuntos.ASIGNADOS, {TipoNegocio.MAIN}),
        (TipoReportePuntos.CANJEADOS, {TipoNegocio.MAIN, TipoNegocio.SOCIO}),
    ],
)
def test_tipos_de_negocio_por_tipo(
    tipo: TipoReportePuntos,
    tipos_negocio: set[TipoNegocio],
) -> None:
    assert ReporteService._TIPOS_NEGOCIO[tipo] == tipos_negocio


@pytest.mark.asyncio
async def test_get_puntos_consolida_dias_sucursales_y_usuarios() -> None:
    main = Negocio(nombre="Main", tipo=TipoNegocio.MAIN)
    socio = Negocio(nombre="Aliado", tipo=TipoNegocio.SOCIO)
    centro = Sucursal(nombre="Centro", negocio_id=main.id)
    eliminada = Sucursal(nombre="Vieja", negocio_id=main.id, is_deleted=True)
    aliada = Sucursal(nombre="Aliada", negocio_id=socio.id)

    ana = _user(nombre="Ana", ci="1")
    beto = _user(nombre="Beto", ci="2")
    carla = _user(nombre="Carla", ci="3", is_deleted=True)
    dario = _user(nombre="Dario", ci="4", role=Role.ADMIN)

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _rows(
                [
                    (date(2026, 11, 1), centro.id, 2, 300, Decimal("30.00")),
                    (date(2026, 11, 3), eliminada.id, 1, 100, Decimal("10.00")),
                ]
            ),
            _rows(
                [
                    (ana.id, 1, 100, Decimal("10.00")),
                    (beto.id, 1, 200, Decimal("20.00")),
                    (carla.id, 1, 100, Decimal("10.00")),
                ]
            ),
            # Orden de la base intencionalmente distinto al esperado.
            _rows([(aliada, socio), (eliminada, main), (centro, main)]),
            _scalars([dario, carla, ana, beto]),
        ]
    )

    data = await ReporteService.get_puntos(session, _query(), _settings())

    # MAIN primero y luego SOCIO; dentro de cada grupo por negocio y nombre.
    assert [s.nombre for s in data.sucursales] == ["Centro", "Vieja", "Aliada"]
    assert [s.eliminada for s in data.sucursales] == [False, True, False]

    # Todos los días del periodo, incluidos los vacíos.
    assert [d.dia for d in data.dias] == [
        date(2026, 11, 1),
        date(2026, 11, 2),
        date(2026, 11, 3),
    ]
    assert data.dias[1].total == ReporteTotales()
    assert data.dias[0].por_sucursal[centro.id].puntos == 300
    assert data.dias[2].por_sucursal[eliminada.id].bs == Decimal("10.00")

    assert data.total == ReporteTotales(cantidad=3, puntos=400, bs=Decimal("40.00"))
    assert data.total_por_sucursal[aliada.id] == ReporteTotales()

    # Bs desc, luego puntos desc, luego nombre; los usuarios con cero al final.
    assert [u.nombre for u in data.usuarios] == ["Beto", "Ana", "Carla", "Dario"]
    assert data.usuarios[2].eliminado is True
    assert data.usuarios[3].totales == ReporteTotales()

    # Ambas hojas cuadran.
    assert sum(u.totales.bs for u in data.usuarios) == data.total.bs
    assert sum(u.totales.cantidad for u in data.usuarios) == data.total.cantidad


@pytest.mark.asyncio
async def test_get_puntos_sin_datos_devuelve_periodo_en_cero() -> None:
    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[_rows([]), _rows([]), _rows([]), _scalars([])]
    )

    data = await ReporteService.get_puntos(
        session,
        _query(TipoReportePuntos.CANJEADOS),
        _settings(),
    )

    assert data.total == ReporteTotales()
    assert len(data.dias) == 3
    assert data.sucursales == []
    assert data.usuarios == []


def test_nombre_archivo() -> None:
    assert ReporteService.nombre_archivo(_query(TipoReportePuntos.CANJEADOS)) == (
        "reporte_puntos_canjeados_2026-11-01_2026-11-03.xlsx"
    )


def test_etiqueta_bs_cambia_segun_tipo() -> None:
    assert ReporteService._etiqueta_bs(TipoReportePuntos.ASIGNADOS) == "Bs compra"
    assert ReporteService._etiqueta_bs(TipoReportePuntos.CANJEADOS) == "Bs vale"


@pytest.mark.asyncio
async def test_generar_excel_crea_dos_hojas_con_totales() -> None:
    main = Negocio(nombre="Main", tipo=TipoNegocio.MAIN)
    centro = Sucursal(nombre="Centro", negocio_id=main.id)
    vieja = Sucursal(nombre="Vieja", negocio_id=main.id, is_deleted=True)
    ana = _user(nombre="Ana", apellidos="Pérez", ci="1")
    luis = _user(nombre="Luis", ci="2", is_deleted=True)

    session = MagicMock()
    session.execute = AsyncMock(
        side_effect=[
            _rows(
                [
                    (date(2026, 11, 1), centro.id, 2, 300, Decimal("30.50")),
                    (date(2026, 11, 2), vieja.id, 1, 50, Decimal("5.00")),
                ]
            ),
            _rows(
                [
                    (ana.id, 2, 300, Decimal("30.50")),
                    (luis.id, 1, 50, Decimal("5.00")),
                ]
            ),
            _rows([(centro, main), (vieja, main)]),
            _scalars([ana, luis]),
        ]
    )
    data = await ReporteService.get_puntos(session, _query(), _settings())

    workbook = load_workbook(BytesIO(ReporteService.generar_excel(data)))

    assert workbook.sheetnames == ["Por sucursal", "Por usuario"]

    sucursales = workbook["Por sucursal"]
    assert sucursales.freeze_panes == "B5"
    assert sucursales["B3"].value == "Main · Centro"
    assert sucursales["E3"].value == "Main · Vieja (eliminada)"
    assert sucursales["H3"].value == "TOTAL SISTEMA"
    assert [sucursales.cell(row=4, column=c).value for c in range(2, 5)] == [
        "Cantidad",
        "Puntos",
        "Bs compra",
    ]
    assert sucursales["A5"].value.date() == date(2026, 11, 1)
    assert sucursales["D5"].number_format == "#,##0.00"
    # Tres días (filas 5 a 7) y la fila de totales.
    assert sucursales["A8"].value == "TOTAL"
    assert [sucursales.cell(row=8, column=c).value for c in range(8, 11)] == [
        3,
        350,
        Decimal("35.50"),
    ]

    usuarios = workbook["Por usuario"]
    assert usuarios.freeze_panes == "A4"
    assert [usuarios.cell(row=3, column=c).value for c in range(1, 7)] == [
        "Usuario",
        "CI",
        "Rol actual",
        "Cantidad",
        "Puntos",
        "Bs compra",
    ]
    assert usuarios["A4"].value == "Ana Pérez"
    assert usuarios["A5"].value == "Luis (eliminado)"
    assert usuarios["A6"].value == "TOTAL"
    assert usuarios["F6"].value == Decimal("35.50")
