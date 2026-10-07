from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.shared.enums import Genero, Role
from app.shared.services.validators import (
    validator_birth_date,
    validator_ci,
    validator_email,
    validator_name,
    validator_password,
    validator_phone,
    validator_required_field,
)


class UserRegistrationData(BaseModel):
    """Schema para auto-registro."""

    ci: str = Field(..., min_length=6, max_length=20)
    telefono: str = Field(..., min_length=6, max_length=20)
    nombre: str = Field(..., min_length=2, max_length=60)
    genero: Genero = Field(default=Genero.O)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return validator_phone(value)

    @field_validator("ci", mode="before")
    @classmethod
    def validate_ci(cls, value: str) -> str:
        return validator_ci(value)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return validator_name(value)

    model_config = ConfigDict(extra="forbid")

class UserCreate(UserRegistrationData):
    """Schema para crear un usuario desde el panel administrativo."""

    role: Role = Field(default=Role.CLIENTE)
    sucursal_id: UUID | None = None

    model_config = ConfigDict(extra="forbid")

class UserSelfUpdate(BaseModel):
    """Schema para actualizar datos del propio usuario."""
    nombre: str | None = Field(default=None, min_length=2, max_length=60)
    apellidos: str | None = Field(default=None, min_length=2, max_length=120)
    telefono: str | None = Field(default=None, min_length=6, max_length=20)
    email: EmailStr | None = Field(default=None)
    birth_date: date | None = Field(default=None)
    direccion: str | None = Field(default=None, min_length=2, max_length=120)
    genero: Genero | None = Field(default=None)

    @field_validator("nombre", "apellidos", mode="before")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        return validator_name(validator_required_field(value))

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_phone(cls, value: str | None) -> str:
        return validator_phone(validator_required_field(value))

    @field_validator("email", mode="before")
    @classmethod
    def validate_email(cls, value: object) -> object:
        if value is None:
            return None
        return validator_email(value)

    @field_validator("birth_date")
    @classmethod
    def validate_birth_date(cls, value: date | None) -> date | None:
        validated = validator_birth_date(value)
        return validated if isinstance(validated, date) else None

    model_config = ConfigDict(extra="forbid")

class UserUpdate(UserSelfUpdate):
    """Schema para actualizar datos de un usuario desde el panel administrativo."""
    ci: str | None = Field(default=None, min_length=6, max_length=20)
    role: Role | None = Field(default=None)
    sucursal_id: UUID | None = Field(default=None)

    @field_validator("ci", mode="before")
    @classmethod
    def validate_ci(cls, value: str | None) -> str:
        return validator_ci(validator_required_field(value))

    @field_validator("role", mode="before")
    @classmethod
    def validate_role(cls, value: Role | None) -> Role:
        return validator_required_field(value)

    model_config = ConfigDict(extra="forbid")


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

    model_config = ConfigDict(from_attributes=True)


class UserResponseAudit(UserResponse):
    """Respuesta de usuario completa con datos de auditoría."""
    created_at: datetime
    created_by: UUID | None
    updated_at: datetime
    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None

    model_config = ConfigDict(from_attributes=True)

class AdminResetPassword(BaseModel):
    """Schema para restablecer contraseñas administrativamente."""

    new_password: str = Field(...,min_length=8, max_length=100)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        return validator_password(value)

    model_config = ConfigDict(extra="forbid")


class PasswordSelfUpdate(AdminResetPassword):
    """Schema para cambiar la contraseña del usuario autenticado."""
    current_password: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")
