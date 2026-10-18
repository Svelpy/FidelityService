from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domains.users.schemas import UserRegistrationData
from app.shared.enums import Role
from app.shared.services.validators import (
    validator_non_empty_text,
    validator_positive_money,
)


class OperacionCreate(BaseModel):
    receptor_id: UUID | None = Field(default=None)
    receptor_data: UserRegistrationData | None = Field(default=None)
    total_compra: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    referencia: str | None = Field(default=None, min_length=1, max_length=255)

    @model_validator(mode="after")
    def validate_receptor(self) -> Self:
        if self.receptor_id is None and self.receptor_data is None:
            raise ValueError(
                "Debe proporcionar receptor_id o receptor_data."
            )
        return self

    @field_validator("total_compra", mode="before")
    @classmethod
    def validate_total_compra(cls, value: object) -> Decimal:
        return validator_positive_money(value)

    @field_validator("referencia", mode="before")
    @classmethod
    def validate_referencia(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "receptor_id": "11111111-1111-4111-8111-111111111111",
                "receptor_data": UserRegistrationData.model_json_schema()["example"],
                "total_compra": "150.00",
                "referencia": "Factura 000123",
            }
        },
    )


class OperacionResponse(BaseModel):
    id: UUID
    receptor_id: UUID
    emisor_id: UUID
    total_compra: Decimal
    total_puntos: int
    config_punto_id: UUID
    sucursal_id: UUID
    referencia: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "receptor_id": "11111111-1111-4111-8111-111111111111",
                "emisor_id": "33333333-3333-4333-8333-333333333333",
                "total_compra": "150.00",
                "total_puntos": 15,
                "config_punto_id": "44444444-4444-4444-8444-444444444444",
                "sucursal_id": "55555555-5555-4555-8555-555555555555",
                "referencia": "Factura 000123",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
            }
        },
    )


class OperacionUsuarioResponse(BaseModel):
    id: UUID
    nombre: str
    apellidos: str | None

    model_config = ConfigDict(from_attributes=True)


class OperacionEmisorResponse(OperacionUsuarioResponse):
    role: Role


class OperacionSucursalResponse(BaseModel):
    id: UUID
    nombre: str

    model_config = ConfigDict(from_attributes=True)


class OperacionListResponse(OperacionResponse):
    receptor: OperacionUsuarioResponse
    emisor: OperacionEmisorResponse
    sucursal: OperacionSucursalResponse

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "22222222-2222-4222-8222-222222222222",
                "receptor_id": "11111111-1111-4111-8111-111111111111",
                "emisor_id": "33333333-3333-4333-8333-333333333333",
                "total_compra": "150.00",
                "total_puntos": 15,
                "config_punto_id": "44444444-4444-4444-8444-444444444444",
                "sucursal_id": "55555555-5555-4555-8555-555555555555",
                "referencia": "Factura 000123",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
                "receptor": {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "nombre": "Carlos",
                    "apellidos": "Pérez López",
                },
                "emisor": {
                    "id": "33333333-3333-4333-8333-333333333333",
                    "nombre": "María",
                    "apellidos": "Gómez Rojas",
                    "role": "CAJERO",
                },
                "sucursal": {
                    "id": "55555555-5555-4555-8555-555555555555",
                    "nombre": "Sucursal Central",
                },
            }
        },
    )


class OperacionResponseAudit(OperacionResponse):

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
                "receptor_id": "11111111-1111-4111-8111-111111111111",
                "emisor_id": "33333333-3333-4333-8333-333333333333",
                "total_compra": "150.00",
                "total_puntos": 15,
                "config_punto_id": "44444444-4444-4444-8444-444444444444",
                "sucursal_id": "55555555-5555-4555-8555-555555555555",
                "referencia": "Factura 000123",
                "created_at": "2026-10-12T14:30:00Z",
                "created_by": "33333333-3333-4333-8333-333333333333",
                "updated_at": "2026-10-12T14:30:00Z",
                "updated_by": "33333333-3333-4333-8333-333333333333",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
