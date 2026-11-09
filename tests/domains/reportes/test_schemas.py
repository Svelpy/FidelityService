from datetime import date

import pytest
from pydantic import ValidationError

from app.domains.reportes.schemas import ReportePuntosQuery
from app.shared.enums import TipoReportePuntos


def test_query_acepta_un_solo_dia() -> None:
    query = ReportePuntosQuery(
        fecha_inicio=date(2026, 11, 1),
        fecha_fin=date(2026, 11, 1),
        tipo=TipoReportePuntos.ASIGNADOS,
    )

    assert query.fecha_inicio == query.fecha_fin


def test_query_acepta_rango_maximo() -> None:
    ReportePuntosQuery(
        fecha_inicio=date(2026, 1, 1),
        fecha_fin=date(2027, 1, 1),
        tipo=TipoReportePuntos.CANJEADOS,
    )


@pytest.mark.parametrize(
    ("fecha_inicio", "fecha_fin"),
    [
        (date(2026, 11, 2), date(2026, 11, 1)),
        (date(2026, 1, 1), date(2027, 1, 2)),
    ],
)
def test_query_rechaza_rangos_invalidos(fecha_inicio: date, fecha_fin: date) -> None:
    with pytest.raises(ValidationError):
        ReportePuntosQuery(
            fecha_inicio=fecha_inicio,
            fecha_fin=fecha_fin,
            tipo=TipoReportePuntos.ASIGNADOS,
        )


def test_query_rechaza_tipo_desconocido() -> None:
    with pytest.raises(ValidationError):
        ReportePuntosQuery(
            fecha_inicio=date(2026, 11, 1),
            fecha_fin=date(2026, 11, 2),
            tipo="OTRO",
        )
