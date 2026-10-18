from app.domains.movimientos_puntos.schemas import (
    MovimientoPuntosListResponse,
    MovimientoPuntosResponse,
    MovimientoPuntosResponseAudit,
)


def test_response_examples_contienen_todos_los_campos() -> None:
    response_example = MovimientoPuntosResponse.model_json_schema()["example"]
    audit_example = MovimientoPuntosResponseAudit.model_json_schema()["example"]

    assert set(response_example) == set(MovimientoPuntosResponse.model_fields)
    assert set(audit_example) == set(MovimientoPuntosResponseAudit.model_fields)


def test_list_response_example_incluye_emisor() -> None:
    example = MovimientoPuntosListResponse.model_json_schema()["example"]

    assert set(example) == set(MovimientoPuntosListResponse.model_fields)
    assert example["emisor"]["role"] == "CAJERO"
