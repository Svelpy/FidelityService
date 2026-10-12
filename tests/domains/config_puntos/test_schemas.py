from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.schemas import (
    ConfigPuntosCreate,
    ConfigPuntosResponse,
)


def _payload() -> dict[str, object]:
    return {
        "asignacion": {"cant_bs": 100, "cant_puntos": 10},
        "costo_vale": {"cant_bs": 50, "cant_puntos": 500},
    }


def test_create_acepta_dos_pares_de_enteros_positivos() -> None:
    data = ConfigPuntosCreate.model_validate(_payload())

    assert data.asignacion.cant_bs == 100
    assert data.asignacion.cant_puntos == 10
    assert data.costo_vale.cant_bs == 50
    assert data.costo_vale.cant_puntos == 500


@pytest.mark.parametrize("invalid_value", [0, -1, True, 1.5, "10"])
def test_create_rechaza_cantidades_invalidas(invalid_value: object) -> None:
    payload = _payload()
    payload["asignacion"] = {
        "cant_bs": invalid_value,
        "cant_puntos": 10,
    }

    with pytest.raises(ValidationError):
        ConfigPuntosCreate.model_validate(payload)


def test_create_rechaza_campos_extra() -> None:
    payload = _payload()
    payload["extra"] = "no permitido"

    with pytest.raises(ValidationError):
        ConfigPuntosCreate.model_validate(payload)


def test_response_se_construye_desde_modelo() -> None:
    config = ConfigPuntos(
        start_date="2026-10-12T14:30:00Z",
        factor_asignacion_puntos=Decimal("0.100000"),
        factor_costo_vale=Decimal("10.000000"),
    )

    response = ConfigPuntosResponse.model_validate(config)

    assert response.id == config.id
    assert response.factor_asignacion_puntos == Decimal("0.100000")
    assert response.factor_costo_vale == Decimal("10.000000")
