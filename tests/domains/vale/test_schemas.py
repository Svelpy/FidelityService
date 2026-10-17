from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.vale.schemas import (
    ValeCreate,
    ValeDetailResponseAudit,
    ValeNegocioCategoriaResponse,
    ValeUpdate,
)


def _data() -> dict[str, object]:
    return {
        "total_costo": "50.00",
        "total_puntos": 450,
        "nombre": " Vale Bs 50 ",
        "descripcion": " Consumo libre ",
        "categoria_id": uuid4(),
        "negocio_id": uuid4(),
    }


def test_create_normaliza_texto_y_conserva_puntos_manuales() -> None:
    vale = ValeCreate.model_validate(_data())
    assert vale.total_costo == Decimal("50.00")
    assert vale.total_puntos == 450
    assert vale.nombre == "Vale Bs 50"
    assert vale.descripcion == "Consumo libre"


@pytest.mark.parametrize("field", ["total_costo", "total_puntos", "nombre"])
def test_create_rechaza_valores_obligatorios_invalidos(field: str) -> None:
    data = _data()
    data[field] = 0 if field != "nombre" else " "
    with pytest.raises(ValidationError):
        ValeCreate.model_validate(data)


def test_update_permite_limpiar_descripcion() -> None:
    data = ValeUpdate(descripcion=None)
    assert data.model_dump(exclude_unset=True) == {"descripcion": None}


@pytest.mark.parametrize(
    "field",
    ["total_costo", "total_puntos", "nombre", "categoria_id", "negocio_id"],
)
def test_update_rechaza_null_en_campos_no_nullables(field: str) -> None:
    with pytest.raises(ValidationError):
        ValeUpdate.model_validate({field: None})


@pytest.mark.parametrize(
    "schema",
    [ValeNegocioCategoriaResponse, ValeDetailResponseAudit],
)
def test_ejemplos_de_respuestas_anidadas_son_validos(schema: type) -> None:
    schema.model_validate(schema.model_json_schema()["example"])
