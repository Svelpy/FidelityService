import pytest
from pydantic import ValidationError

from app.domains.negocio.schemas import (
    NegocioCreate,
    NegocioResponse,
    NegocioResponseAudit,
    NegocioUpdate,
)
from app.shared.enums import TipoNegocio


def test_negocio_create_normaliza_campos() -> None:
    data = NegocioCreate(
        nombre="  Café Central  ",
        tipo=TipoNegocio.SOCIO,
        descripcion="  Cafetería artesanal.  ",
        telefono=" 71234567 ",
    )

    assert data.nombre == "Café Central"
    assert data.descripcion == "Cafetería artesanal."
    assert data.telefono == "71234567"


@pytest.mark.parametrize("field", ["nombre", "tipo"])
def test_negocio_update_rechaza_null_en_campos_no_nullable(field: str) -> None:
    with pytest.raises(ValidationError):
        NegocioUpdate.model_validate({field: None})


@pytest.mark.parametrize("field", ["descripcion", "telefono"])
def test_negocio_update_conserva_null_en_campos_nullable(field: str) -> None:
    data = NegocioUpdate.model_validate({field: None})

    assert data.model_dump(exclude_unset=True) == {field: None}


@pytest.mark.parametrize("telefono", ["12345", "123456789012345678901", "abc123"])
def test_negocio_rechaza_telefono_invalido(telefono: str) -> None:
    with pytest.raises(ValidationError):
        NegocioCreate(
            nombre="Café Central",
            tipo=TipoNegocio.SOCIO,
            telefono=telefono,
        )


def test_negocio_no_acepta_image_url_en_create() -> None:
    with pytest.raises(ValidationError):
        NegocioCreate.model_validate(
            {
                "nombre": "Café Central",
                "tipo": "SOCIO",
                "image_url": "https://example.com/logo.jpg",
            }
        )


def test_negocio_responses_incluyen_ejemplos_json_schema() -> None:
    response_example = NegocioResponse.model_json_schema()["example"]
    audit_example = NegocioResponseAudit.model_json_schema()["example"]

    assert response_example["image_url"].startswith("https://res.cloudinary.com/")
    assert audit_example["created_by"] == "22222222-2222-4222-8222-222222222222"
    assert audit_example["is_deleted"] is False
