from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.operacion.schemas import (
    OperacionCreate,
    OperacionResponse,
    OperacionResponseAudit,
)


def test_create_normaliza_importe_y_referencia() -> None:
    data = OperacionCreate(
        receptor_id=uuid4(),
        total_compra="150.50",
        referencia="  Factura 123  ",
    )

    assert data.total_compra == Decimal("150.50")
    assert data.referencia == "Factura 123"


@pytest.mark.parametrize("value", [None, 0, -1, "", "no-numero", True])
def test_create_rechaza_importe_invalido(value: object) -> None:
    with pytest.raises(ValidationError):
        OperacionCreate(receptor_id=uuid4(), total_compra=value)


def test_create_rechaza_campos_calculados() -> None:
    with pytest.raises(ValidationError):
        OperacionCreate.model_validate(
            {
                "receptor_id": str(uuid4()),
                "total_compra": "100.00",
                "total_puntos": 10,
            }
        )


def test_response_examples_contienen_todos_los_campos() -> None:
    response_fields = set(OperacionResponse.model_fields)
    audit_fields = set(OperacionResponseAudit.model_fields)

    response_example = OperacionResponse.model_json_schema()["example"]
    audit_example = OperacionResponseAudit.model_json_schema()["example"]

    assert set(response_example) == response_fields
    assert set(audit_example) == audit_fields
