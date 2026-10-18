from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.operacion.schemas import (
    OperacionCreate,
    OperacionDetailResponse,
    OperacionDetailResponseAudit,
    OperacionListResponse,
    OperacionListResponseAudit,
    OperacionResponse,
    OperacionResponseAudit,
)


def _receptor_data() -> dict[str, object]:
    return {
        "ci": "12345678",
        "telefono": "71234567",
        "nombre": "Ana",
        "genero": "F",
    }


def test_create_normaliza_importe_y_referencia() -> None:
    data = OperacionCreate(
        receptor_id=uuid4(),
        receptor_data=_receptor_data(),
        total_compra="150.50",
        referencia="  Factura 123  ",
    )

    assert data.total_compra == Decimal("150.50")
    assert data.referencia == "Factura 123"


def test_create_permite_receptor_existente_sin_datos_de_registro() -> None:
    receptor_id = uuid4()

    data = OperacionCreate(
        receptor_id=receptor_id,
        total_compra="100.00",
    )

    assert data.receptor_id == receptor_id
    assert data.receptor_data is None


def test_create_permite_registrar_receptor_sin_id() -> None:
    data = OperacionCreate(
        receptor_data=_receptor_data(),
        total_compra="100.00",
    )

    assert data.receptor_id is None
    assert data.receptor_data is not None


def test_create_requiere_id_o_datos_del_receptor() -> None:
    with pytest.raises(ValidationError):
        OperacionCreate(total_compra="100.00")


def test_create_valida_datos_del_nuevo_receptor() -> None:
    with pytest.raises(ValidationError):
        OperacionCreate(
            receptor_data={**_receptor_data(), "telefono": "invalido"},
            total_compra="100.00",
        )


@pytest.mark.parametrize("value", [None, 0, -1, "", "no-numero", True])
def test_create_rechaza_importe_invalido(value: object) -> None:
    with pytest.raises(ValidationError):
        OperacionCreate(
            receptor_id=uuid4(),
            receptor_data=_receptor_data(),
            total_compra=value,
        )


def test_create_rechaza_campos_calculados() -> None:
    with pytest.raises(ValidationError):
        OperacionCreate.model_validate(
            {
                "receptor_id": str(uuid4()),
                "receptor_data": _receptor_data(),
                "total_compra": "100.00",
                "total_puntos": 10,
            }
        )


def test_response_examples_contienen_todos_los_campos() -> None:
    create_fields = set(OperacionCreate.model_fields)
    response_fields = set(OperacionResponse.model_fields)
    audit_fields = set(OperacionResponseAudit.model_fields)

    create_example = OperacionCreate.model_json_schema()["example"]
    response_example = OperacionResponse.model_json_schema()["example"]
    audit_example = OperacionResponseAudit.model_json_schema()["example"]

    assert set(create_example) == create_fields
    assert set(response_example) == response_fields
    assert set(audit_example) == audit_fields


@pytest.mark.parametrize(
    ("schema", "fields"),
    [
        (
            OperacionListResponse,
            {"operacion", "receptor", "emisor", "sucursal"},
        ),
        (
            OperacionListResponseAudit,
            {"operacion", "receptor", "emisor", "sucursal"},
        ),
        (
            OperacionDetailResponse,
            {"operacion", "receptor", "emisor", "sucursal", "negocio"},
        ),
        (
            OperacionDetailResponseAudit,
            {"operacion", "receptor", "emisor", "sucursal", "negocio"},
        ),
    ],
)
def test_responses_compuestas_tienen_estructura_y_ejemplo_validos(
    schema: type[OperacionListResponse],
    fields: set[str],
) -> None:
    example = schema.model_json_schema()["example"]

    assert set(schema.model_fields) == fields
    assert set(example) == fields
    schema.model_validate(example)
