from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.services.validators import (
    validator_http_url,
    validator_non_empty_text,
    validator_phone,
)


class SucursalCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    negocio_id: UUID =Field(...)
    direccion: str | None = Field(default=None, min_length=1, max_length=255)
    url_ubicacion: str | None = Field(default=None, min_length=1, max_length=2048, pattern=r"^https?://.+$")
    telefono: str | None = Field(default=None, min_length=6, max_length=20, pattern=r"^(?:\d{6,20}|\+\d{6,19})$")

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_non_empty_text(value)

    @field_validator("negocio_id")
    @classmethod
    def validate_negocio_id(cls, value: UUID | None) -> UUID:
        if value is None:
            raise ValueError("El negocio no puede ser null.")
        return value

    @field_validator("direccion", mode="before")
    @classmethod
    def validate_direccion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

    @field_validator("url_ubicacion", mode="before")
    @classmethod
    def validate_url_ubicacion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_http_url(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_telefono(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_phone(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nombre": "Sucursal Equipetrol",
                "negocio_id": "11111111-1111-4111-8111-111111111111",
                "direccion": "Av. San Martín 123",
                "url_ubicacion": "https://maps.google.com/?q=-17.77,-63.20",
                "telefono": "71234567",
            }
        },
    )


class SucursalUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    negocio_id: UUID | None = Field(default=None)
    direccion: str | None = Field(default=None, min_length=1, max_length=255)
    url_ubicacion: str | None = Field(default=None, min_length=1, max_length=2048, pattern=r"^https?://.+$")
    telefono: str | None = Field(default=None, min_length=6, max_length=20, pattern=r"^(?:\d{6,20}|\+\d{6,19})$")

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_non_empty_text(value)

    @field_validator("negocio_id")
    @classmethod
    def validate_negocio_id(cls, value: UUID | None) -> UUID:
        if value is None:
            raise ValueError("El negocio no puede ser null.")
        return value

    @field_validator("direccion", mode="before")
    @classmethod
    def validate_direccion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

    @field_validator("url_ubicacion", mode="before")
    @classmethod
    def validate_url_ubicacion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_http_url(value)

    @field_validator("telefono", mode="before")
    @classmethod
    def validate_telefono(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_phone(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "nombre": "Sucursal Equipetrol Norte",
                "negocio_id": "11111111-1111-4111-8111-111111111111",
                "direccion": None,
                "url_ubicacion": "https://maps.google.com/?q=-17.76,-63.19",
                "telefono": "72123456",
            }
        },
    )


class SucursalResponse(BaseModel):
    id: UUID
    nombre: str
    negocio_id: UUID
    direccion: str | None
    url_ubicacion: str | None
    telefono: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "nombre": "Sucursal Equipetrol",
                "negocio_id": "11111111-1111-4111-8111-111111111111",
                "direccion": "Av. San Martín 123",
                "url_ubicacion": "https://maps.google.com/?q=-17.77,-63.20",
                "telefono": "71234567",
                "created_at": "2026-10-12T12:00:00Z",
                "updated_at": "2026-10-12T12:00:00Z",
            }
        },
    )


class SucursalResponseAudit(SucursalResponse):

    created_by: UUID | None
    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "nombre": "Sucursal Equipetrol",
                "negocio_id": "11111111-1111-4111-8111-111111111111",
                "direccion": "Av. San Martín 123",
                "url_ubicacion": "https://maps.google.com/?q=-17.77,-63.20",
                "telefono": "71234567",
                "created_at": "2026-10-12T12:00:00Z",
                "created_by": "33333333-3333-4333-8333-333333333333",
                "updated_at": "2026-10-12T12:00:00Z",
                "updated_by": "33333333-3333-4333-8333-333333333333",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
