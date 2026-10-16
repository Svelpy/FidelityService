import pytest
from pydantic import ValidationError

from app.domains.config_puntos.models import ConfigPuntos
from app.domains.config_puntos.schemas import (
    ConfigPuntosCreate,
    ConfigPuntosResponse,
)
from app.shared.enums import EstadoConfigPuntos


def _payload() -> dict[str, object]:
    return {
        "asignacion": {"bolivianos": 100, "puntos": 10},
        "costo_vale": {"bolivianos": 50, "puntos": 500},
    }


def test_create_acepta_dos_pares_de_enteros_positivos() -> None:
    data = ConfigPuntosCreate.model_validate(_payload())

    assert data.asignacion.bolivianos == 100
    assert data.asignacion.puntos == 10
    assert data.costo_vale.bolivianos == 50
    assert data.costo_vale.puntos == 500


@pytest.mark.parametrize("invalid_value", [0, -1, True, 1.5, "10"])
def test_create_rechaza_cantidades_invalidas(invalid_value: object) -> None:
    payload = _payload()
    payload["asignacion"] = {
        "bolivianos": invalid_value,
        "puntos": 10,
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
        asignacion_bolivianos=100,
        asignacion_puntos=10,
        costo_vale_bolivianos=50,
        costo_vale_puntos=500,
        status=EstadoConfigPuntos.ACTIVE,
    )

    response = ConfigPuntosResponse.model_validate(config)

    assert response.id == config.id
    assert response.asignacion_bolivianos == 100
    assert response.asignacion_puntos == 10
    assert response.costo_vale_bolivianos == 50
    assert response.costo_vale_puntos == 500
    assert response.status is EstadoConfigPuntos.ACTIVE
