from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.sucursal.schemas import (
    SucursalCreate,
    SucursalResponse,
    SucursalResponseAudit,
    SucursalUpdate,
)


def test_sucursal_create_normaliza_campos() -> None:
    data = SucursalCreate(
        nombre="  Sucursal Equipetrol  ",
        negocio_id=uuid4(),
        direccion="  Av. San Martín 123  ",
        url_ubicacion="  https://maps.google.com/?q=-17.77,-63.20  ",
        telefono=" 71234567 ",
    )

    assert data.nombre == "Sucursal Equipetrol"
    assert data.direccion == "Av. San Martín 123"
    assert data.url_ubicacion == "https://maps.google.com/?q=-17.77,-63.20"
    assert data.telefono == "71234567"


@pytest.mark.parametrize("field", ["nombre", "negocio_id"])
def test_sucursal_update_rechaza_null_en_campos_no_nullable(field: str) -> None:
    with pytest.raises(ValidationError):
        SucursalUpdate.model_validate({field: None})


@pytest.mark.parametrize("field", ["direccion", "url_ubicacion", "telefono"])
def test_sucursal_update_conserva_null_en_campos_nullable(field: str) -> None:
    data = SucursalUpdate.model_validate({field: None})

    assert data.model_dump(exclude_unset=True) == {field: None}


@pytest.mark.parametrize("telefono", ["12345", "123456789012345678901", "abc123"])
def test_sucursal_rechaza_telefono_invalido(telefono: str) -> None:
    with pytest.raises(ValidationError):
        SucursalCreate(
            nombre="Sucursal Equipetrol",
            negocio_id=uuid4(),
            telefono=telefono,
        )


@pytest.mark.parametrize(
    "url",
    ["maps.google.com/ubicacion", "ftp://example.com/mapa", "sin-url"],
)
def test_sucursal_rechaza_url_ubicacion_invalida(url: str) -> None:
    with pytest.raises(ValidationError):
        SucursalCreate(
            nombre="Sucursal Equipetrol",
            negocio_id=uuid4(),
            url_ubicacion=url,
        )


def test_sucursal_create_rechaza_campos_desconocidos() -> None:
    with pytest.raises(ValidationError):
        SucursalCreate.model_validate(
            {
                "nombre": "Sucursal Equipetrol",
                "negocio_id": str(uuid4()),
                "is_deleted": True,
            }
        )


def test_sucursal_responses_incluyen_ejemplos_json_schema() -> None:
    response_example = SucursalResponse.model_json_schema()["example"]
    audit_example = SucursalResponseAudit.model_json_schema()["example"]

    assert response_example["url_ubicacion"].startswith("https://")
    assert audit_example["created_by"] == "33333333-3333-4333-8333-333333333333"
    assert audit_example["is_deleted"] is False
