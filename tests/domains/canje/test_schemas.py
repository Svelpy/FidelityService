from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.canje.schemas import (
    CanjeByCodigoResponse,
    CanjeCreate,
    CanjeDetailResponse,
    CanjeDetailResponseAudit,
    CanjeListResponse,
    CanjeListResponseAudit,
    CanjeResponse,
    CanjeResponseAudit,
)


def test_create_normaliza_referencia() -> None:
    data = CanjeCreate(
        vale_id=uuid4(),
        referencia="  Aplicación móvil  ",
    )

    assert data.referencia == "Aplicación móvil"


def test_create_referencia_es_opcional_y_puede_quedar_vacia() -> None:
    assert CanjeCreate(vale_id=uuid4()).referencia is None
    assert CanjeCreate(vale_id=uuid4(), referencia="   ").referencia is None
    assert CanjeCreate(vale_id=uuid4(), referencia=None).referencia is None


def test_create_rechaza_dador_y_sucursal_enviados_por_cliente() -> None:
    with pytest.raises(ValidationError):
        CanjeCreate.model_validate(
            {
                "vale_id": str(uuid4()),
                "referencia": None,
                "dador_id": str(uuid4()),
                "sucursal_id": str(uuid4()),
            }
        )


def test_response_examples_contienen_todos_los_campos() -> None:
    response_example = CanjeResponse.model_json_schema()["example"]
    audit_example = CanjeResponseAudit.model_json_schema()["example"]

    assert set(response_example) == set(CanjeResponse.model_fields)
    assert set(audit_example) == set(CanjeResponseAudit.model_fields)


def test_by_codigo_response_reutiliza_examples_hijos() -> None:
    example = CanjeByCodigoResponse.model_json_schema()["example"]

    assert set(example) == {"canje", "vale", "negocio", "usuario_cliente"}
    assert example["usuario_cliente"]["id"] == example["canje"]["cliente_id"]
    assert example["vale"]["id"] == example["canje"]["vale_id"]
    assert example["negocio"]["id"] == example["vale"]["negocio_id"]
    CanjeByCodigoResponse.model_validate(example)


@pytest.mark.parametrize(
    "schema",
    [CanjeDetailResponse, CanjeDetailResponseAudit],
)
def test_canje_detail_responses_reutilizan_examples_hijos(
    schema: type[CanjeDetailResponse],
) -> None:
    example = schema.model_json_schema()["example"]

    assert set(example) == {
        "canje",
        "usuario_cliente",
        "usuario_cajero_socio",
        "vale",
        "sucursal",
        "negocio",
    }
    assert example["usuario_cajero_socio"]["role"] == "CAJERO"
    assert example["sucursal"]["id"] == example["canje"]["sucursal_id"]
    schema.model_validate(example)


@pytest.mark.parametrize(
    "schema",
    [CanjeListResponse, CanjeListResponseAudit],
)
def test_canje_list_responses_reutilizan_examples_hijos(
    schema: type[CanjeListResponse],
) -> None:
    example = schema.model_json_schema()["example"]

    assert set(example) == {"canje", "vale", "sucursal", "negocio"}
    assert example["sucursal"]["id"] == example["canje"]["sucursal_id"]
    schema.model_validate(example)
