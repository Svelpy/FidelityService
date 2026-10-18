from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.sucursal.schemas import SucursalResponse, SucursalResponseAudit
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
                "descripcion": "Cafetería y restaurante de especialidad.",
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
    created_at: datetime
    updated_at: datetime
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
                "updated_at": "2026-10-11T15:00:00Z",
            }
        },
    )


class NegocioResponseAudit(NegocioResponse):
    created_by: UUID | None
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
                "is_deleted": True,
                "deleted_at": "2026-10-13T10:15:00Z",
                "deleted_by": "33333333-3333-4333-8333-333333333333",
            }
        },
    )


class NegocioSucursalesResponse(BaseModel):
    negocio: NegocioResponse
    sucursales: list[SucursalResponse]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "negocio": NegocioResponse.model_json_schema()["example"],
                "sucursales": [
                    SucursalResponse.model_json_schema()["example"]
                ],
            }
        },
    )


class NegocioSucursalesResponseAudit(NegocioSucursalesResponse):
    negocio: NegocioResponseAudit
    sucursales: list[SucursalResponseAudit]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "negocio": NegocioResponseAudit.model_json_schema()["example"],
                "sucursales": [
                    SucursalResponseAudit.model_json_schema()["example"]
                ],
            }
        },
    )
