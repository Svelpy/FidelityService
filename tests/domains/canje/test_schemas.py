from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.canje.schemas import (
    CanjeCreate,
    CanjeRedeem,
    CanjeResponse,
    CanjeResponseAudit,
    CanjeValeNegocioResponse,
    CanjeValeResponse,
    CanjeValeResponseAudit,
)
from app.domains.negocio.schemas import NegocioResponse
from app.domains.vale.schemas import ValeResponse, ValeResponseAudit


def test_create_normaliza_referencia() -> None:
    data = CanjeCreate(
        vale_id=uuid4(),
        referencia="  Aplicación móvil  ",
    )

    assert data.referencia == "Aplicación móvil"


@pytest.mark.parametrize(
    "code",
    [12345678, "1234567", "123456789", "12A45678", "１２３４５６７８", ""],
)
def test_redeem_rechaza_codigo_invalido(code: object) -> None:
    with pytest.raises(ValidationError):
        CanjeRedeem(codigo_canje=code)


def test_redeem_conserva_ceros_iniciales() -> None:
    assert CanjeRedeem(codigo_canje="00123456").codigo_canje == "00123456"


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


def test_canje_vale_response_reutiliza_examples_hijos() -> None:
    example = CanjeValeResponse.model_json_schema()["example"]

    assert example == {
        "canje": CanjeResponse.model_json_schema()["example"],
        "vale": ValeResponse.model_json_schema()["example"],
    }
    CanjeValeResponse.model_validate(example)


def test_canje_vale_response_audit_reutiliza_examples_hijos() -> None:
    example = CanjeValeResponseAudit.model_json_schema()["example"]

    assert example == {
        "canje": CanjeResponseAudit.model_json_schema()["example"],
        "vale": ValeResponseAudit.model_json_schema()["example"],
    }
    CanjeValeResponseAudit.model_validate(example)


def test_canje_vale_negocio_response_reutiliza_examples_hijos() -> None:
    example = CanjeValeNegocioResponse.model_json_schema()["example"]

    assert example == {
        "canje": CanjeResponse.model_json_schema()["example"],
        "vale": ValeResponse.model_json_schema()["example"],
        "negocio": NegocioResponse.model_json_schema()["example"],
    }
    CanjeValeNegocioResponse.model_validate(example)
