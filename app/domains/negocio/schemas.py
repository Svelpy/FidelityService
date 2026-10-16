from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.enums import TipoNegocio
from app.shared.services.validators import (
    validator_non_empty_text,
    validator_phone,
)


class NegocioCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=60)
    tipo: TipoNegocio = Field(...)
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    telefono: str | None = Field(default=None, min_length=6, max_length=20, pattern=r"^(?:\d{6,20}|\+\d{6,19})$")

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_non_empty_text(value)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, value: TipoNegocio | None) -> TipoNegocio:
        if value is None:
            raise ValueError("El tipo de negocio no puede ser null.")
        return value

    @field_validator("descripcion", mode="before")
    @classmethod
    def validate_descripcion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

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
                "nombre": "Café Central",
                "tipo": "SOCIO",
                "descripcion": "Cafetería y pastelería artesanal.",
                "telefono": "71234567",
            }
        },
    )


class NegocioUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    tipo: TipoNegocio | None = Field(default=None)
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    telefono: str | None = Field(default=None, min_length=6, max_length=20, pattern=r"^(?:\d{6,20}|\+\d{6,19})$")

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_non_empty_text(value)

    @field_validator("tipo")
    @classmethod
    def validate_tipo(cls, value: TipoNegocio | None) -> TipoNegocio:
        if value is None:
            raise ValueError("El tipo de negocio no puede ser null.")
        return value

    @field_validator("descripcion", mode="before")
    @classmethod
    def validate_descripcion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

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
                "nombre": "Café Central Equipetrol",
                "tipo": "SOCIO",
                "descripcion": None,
                "telefono": "72123456",
            }
        },
    )


class NegocioResponse(BaseModel):
    id: UUID
    nombre: str
    tipo: TipoNegocio
    descripcion: str | None
    telefono: str | None
    image_url: str | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "nombre": "Café Central",
                "tipo": "SOCIO",
                "descripcion": "Cafetería y pastelería artesanal.",
                "telefono": "71234567",
                "image_url": "https://res.cloudinary.com/demo/image/upload/negocios/cafe.jpg",
            }
        },
    )


class NegocioResponseAudit(NegocioResponse):
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
                "nombre": "Café Central",
                "tipo": "SOCIO",
                "descripcion": "Cafetería y pastelería artesanal.",
                "telefono": "71234567",
                "image_url": "https://res.cloudinary.com/demo/image/upload/negocios/cafe.jpg",
                "created_at": "2026-10-11T14:30:00Z",
                "created_by": "22222222-2222-4222-8222-222222222222",
                "updated_at": "2026-10-11T15:00:00Z",
                "updated_by": "22222222-2222-4222-8222-222222222222",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
