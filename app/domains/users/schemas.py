from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.enums import Genero, Role
from app.shared.services.validators import (
    validator_address,
    validator_birth_date,
    validator_ci,
    validator_email,
    validator_name,
    validator_password,
    validator_phone,
)


class UserRegistrationData(BaseModel):
    """Schema para auto-registro."""
    #OBLIGATORIOS
    ci: str = Field(..., min_length=6, max_length=20)
    telefono: str = Field(..., min_length=6, max_length=20)
    nombre: str = Field(..., min_length=2, max_length=60)
    #OPCIONALES
    genero: Genero = Field(default=Genero.O)
    apellidos: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = Field(default=None)
    birth_date: date | None = Field(default=None)
    direccion: str | None = Field(default=None, min_length=2, max_length=120)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str:
        if value is None:
            raise ValueError("El teléfono no puede ser null.")
        return validator_phone(value)

    @field_validator("ci", mode="before")
    @classmethod
    def validate_ci(cls, value: object) -> str:
        if value is None:
            raise ValueError("La cédula de identidad no puede ser null.")
        return validator_ci(value)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_name(value)

    @field_validator("genero")
    @classmethod
    def validate_gender(cls, value: Genero | None) -> Genero:
        if value is None:
            raise ValueError("El género no puede ser null.")
        return value

    @field_validator("apellidos", mode="before")
    @classmethod
    def validate_last_name(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_email(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return validator_birth_date(value)

    @field_validator("direccion", mode="before")
    @classmethod
    def validate_address(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_address(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "ci": "12345678",
                "telefono": "71234567",
                "nombre": "Ana",
                "genero": "F",
                "apellidos": "Pérez López",
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "direccion": "Avenida Principal 123",
            }
        },
    )

class UserCreate(UserRegistrationData):
    """Schema para crear un usuario desde el panel administrativo."""
    #OBLIGATORIOS
    role: Role = Field(...)
    #OPCIONALES
    sucursal_id: UUID | None = Field(default=None)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Role | None) -> Role:
        if value is None:
            raise ValueError("El rol no puede ser null.")
        return value

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "ci": "12345678",
                "telefono": "71234567",
                "nombre": "Ana",
                "genero": "F",
                "apellidos": "Pérez López",
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "direccion": "Avenida Principal 123",
                "role": "CLIENTE",
                "sucursal_id": None,
            }
        },
    )

class UserSelfUpdate(BaseModel):
    """Schema para actualizar datos del propio usuario."""
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    telefono: str | None = Field(default=None, min_length=6, max_length=20)

    genero: Genero | None = Field(default=None)
    apellidos: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = Field(default=None)
    birth_date: date | None = Field(default=None)
    direccion: str | None = Field(default=None, min_length=2, max_length=120)


    @field_validator("nombre", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_name(value)

    @field_validator("apellidos", mode="before")
    @classmethod
    def validate_last_name(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_name(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_phone(cls, value: object) -> str:
        if value is None:
            raise ValueError("El teléfono no puede ser null.")
        return validator_phone(value)

    @field_validator("genero")
    @classmethod
    def validate_gender(cls, value: Genero | None) -> Genero:
        if value is None:
            raise ValueError("El género no puede ser null.")
        return value

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_email(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        if value is None:
            return None
        return validator_birth_date(value)

    @field_validator("direccion", mode="before")
    @classmethod
    def validate_address(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_address(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nombre": "Ana María",
                "telefono": "71234567",
                "genero": "F",
                "apellidos": None,
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "direccion": "Avenida Principal 123",
            }
        },
    )

class UserUpdate(UserSelfUpdate):
    """Schema para actualizar datos de un usuario desde el panel administrativo."""
    ci: str | None = Field(default=None, min_length=6, max_length=20)
    role: Role | None = Field(default=None)
    sucursal_id: UUID | None = Field(default=None)

    @field_validator("ci", mode="before")
    @classmethod
    def validate_ci(cls, value: object) -> str:
        if value is None:
            raise ValueError("La cédula de identidad no puede ser null.")
        return validator_ci(value)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: Role | None) -> Role:
        if value is None:
            raise ValueError("El rol no puede ser null.")
        return value

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nombre": "Ana María",
                "telefono": "71234567",
                "genero": "F",
                "apellidos": None,
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "direccion": "Avenida Principal 123",
                "ci": "12345678",
                "role": "CLIENTE",
                "sucursal_id": None,
            }
        },
    )


class UserResponse(BaseModel):
    """Respuesta de usuario sin contraseña ni datos sensibles."""
    id: UUID
    nombre: str
    apellidos: str | None
    telefono: str
    email: EmailStr | None
    birth_date: date | None
    ci: str
    direccion: str | None
    avatar_url: str | None
    genero: Genero
    role: Role
    puntos: int
    sucursal_id: UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "nombre": "Ana",
                "apellidos": "Pérez López",
                "telefono": "71234567",
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "ci": "12345678",
                "direccion": "Avenida Principal 123",
                "avatar_url": "https://res.cloudinary.com/demo/image/upload/avatar.jpg",
                "genero": "F",
                "role": "CLIENTE",
                "puntos": 150,
                "sucursal_id": None,
            }
        },
    )


class UserResponseAudit(UserResponse):
    """Respuesta de usuario completa con datos de auditoría."""
    created_at: datetime
    created_by: UUID | None
    updated_at: datetime
    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "nombre": "Ana",
                "apellidos": "Pérez López",
                "telefono": "71234567",
                "email": "ana@example.com",
                "birth_date": "1995-04-18",
                "ci": "12345678",
                "direccion": "Avenida Principal 123",
                "avatar_url": "https://res.cloudinary.com/demo/image/upload/avatar.jpg",
                "genero": "F",
                "role": "CLIENTE",
                "puntos": 150,
                "sucursal_id": None,
                "created_at": "2026-10-08T14:30:00Z",
                "created_by": "22222222-2222-4222-8222-222222222222",
                "updated_at": "2026-10-08T15:00:00Z",
                "updated_by": "22222222-2222-4222-8222-222222222222",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )

class AdminResetPassword(BaseModel):
    """Schema para restablecer contraseñas administrativamente."""

    new_password: str = Field(..., min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validator_password(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "new_password": "NuevaClave123",
            }
        },
    )


class PasswordSelfUpdate(AdminResetPassword):
    """Schema para cambiar la contraseña del usuario autenticado."""
    current_password: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "new_password": "NuevaClave123",
                "current_password": "ClaveActual123",
            }
        },
    )
