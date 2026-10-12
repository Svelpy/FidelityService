from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domains.users.schemas import (
    AdminResetPassword,
    UserCreate,
    UserRegistrationData,
    UserResponse,
    UserResponseAudit,
    UserSelfUpdate,
    UserUpdate,
)
from app.shared.enums import Genero, Role


def _registration_data(**overrides: object) -> dict[str, object]:
    values: dict[str, object] = {
        "ci": "12345678",
        "telefono": "71234567",
        "nombre": "Ana",
        "genero": Genero.F,
    }
    values.update(overrides)
    return values


def test_registration_normaliza_datos() -> None:
    data = UserRegistrationData.model_validate(
        _registration_data(
            ci=" 12345678 ",
            telefono=" 71234567 ",
            nombre="  Ana María  ",
            apellidos="  Pérez López  ",
            email="  ANA@EXAMPLE.COM ",
            direccion="  Avenida Principal 123  ",
        )
    )

    assert data.ci == "12345678"
    assert data.telefono == "71234567"
    assert data.nombre == "Ana María"
    assert data.apellidos == "Pérez López"
    assert str(data.email) == "ana@example.com"
    assert data.direccion == "Avenida Principal 123"


@pytest.mark.parametrize("field", ["nombre", "telefono", "genero"])
def test_self_update_rechaza_null_no_nullable(field: str) -> None:
    with pytest.raises(ValidationError):
        UserSelfUpdate.model_validate({field: None})


@pytest.mark.parametrize("field", ["apellidos", "email", "birth_date", "direccion"])
def test_self_update_conserva_null_nullable(field: str) -> None:
    data = UserSelfUpdate.model_validate({field: None})

    assert data.model_dump(exclude_unset=True) == {field: None}


@pytest.mark.parametrize("field", ["ci", "role"])
def test_admin_update_rechaza_null_no_nullable(field: str) -> None:
    with pytest.raises(ValidationError):
        UserUpdate.model_validate({field: None})


def test_admin_update_permite_limpiar_sucursal() -> None:
    data = UserUpdate(sucursal_id=None)

    assert data.model_dump(exclude_unset=True) == {"sucursal_id": None}


def test_user_create_rechaza_avatar_y_puntos() -> None:
    with pytest.raises(ValidationError):
        UserCreate.model_validate(
            {
                **_registration_data(),
                "role": Role.CLIENTE,
                "avatar_url": "https://example.com/avatar.jpg",
                "puntos": 100,
            }
        )


def test_password_administrativa_exige_seis_caracteres() -> None:
    with pytest.raises(ValidationError):
        AdminResetPassword(new_password="12345")

    assert AdminResetPassword(new_password="123456").new_password == "123456"


def test_user_responses_incluyen_json_schema() -> None:
    response_example = UserResponse.model_json_schema()["example"]
    audit_example = UserResponseAudit.model_json_schema()["example"]

    assert response_example["avatar_url"].startswith("https://")
    assert audit_example["created_by"] == "22222222-2222-4222-8222-222222222222"
    assert audit_example["is_deleted"] is False


def test_registration_rechaza_campos_internos() -> None:
    with pytest.raises(ValidationError):
        UserRegistrationData.model_validate(
            {**_registration_data(), "role": Role.SUPERADMIN}
        )
