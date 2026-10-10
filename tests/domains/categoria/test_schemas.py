import pytest
from pydantic import ValidationError

from app.domains.categoria.schemas import (
    CategoriaCreate,
    CategoriaResponse,
    CategoriaResponseAudit,
    CategoriaUpdate,
)


def test_categoria_create_normaliza_texto() -> None:
    data = CategoriaCreate(
        nombre="  Gastronomia  ",
        icon_number=3,
        descripcion="  Restaurantes y cafeterias.  ",
    )

    assert data.nombre == "Gastronomia"
    assert data.descripcion == "Restaurantes y cafeterias."


@pytest.mark.parametrize("field", ["nombre", "icon_number"])
def test_categoria_update_rechaza_null_en_campos_no_nullable(field: str) -> None:
    with pytest.raises(ValidationError):
        CategoriaUpdate.model_validate({field: None})


def test_categoria_update_distingue_descripcion_omitida_y_null() -> None:
    omitted = CategoriaUpdate()
    explicit_null = CategoriaUpdate(descripcion=None)

    assert omitted.model_dump(exclude_unset=True) == {}
    assert explicit_null.model_dump(exclude_unset=True) == {"descripcion": None}


@pytest.mark.parametrize("icon_number", [-1, True, "3"])
def test_categoria_rechaza_numero_de_icono_invalido(icon_number: object) -> None:
    with pytest.raises(ValidationError):
        CategoriaCreate(
            nombre="Gastronomia",
            icon_number=icon_number,
        )


@pytest.mark.parametrize("nombre", ["!!!", "---", "...", "   "])
def test_categoria_rechaza_nombre_que_no_genera_slug(nombre: str) -> None:
    with pytest.raises(ValidationError):
        CategoriaCreate(nombre=nombre)

    with pytest.raises(ValidationError):
        CategoriaUpdate(nombre=nombre)


def test_categoria_permite_signos_en_descripcion() -> None:
    data = CategoriaCreate(nombre="Gastronomia", descripcion="!!!")

    assert data.descripcion == "!!!"


def test_categoria_response_incluye_ejemplo_json_schema() -> None:
    example = CategoriaResponse.model_json_schema()["example"]

    assert example["slug"] == "gastronomia"
    assert example["icon_number"] == 3


def test_categoria_response_audit_incluye_ejemplo_json_schema() -> None:
    example = CategoriaResponseAudit.model_json_schema()["example"]

    assert example["created_by"] == "22222222-2222-4222-8222-222222222222"
    assert example["is_deleted"] is False
    assert example["deleted_at"] is None
