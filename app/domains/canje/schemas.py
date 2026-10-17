from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.negocio.schemas import NegocioResponse, NegocioResponseAudit
from app.domains.sucursal.schemas import SucursalResponse, SucursalResponseAudit
from app.domains.users.schemas import UserResponse, UserResponseAudit
from app.domains.vale.schemas import ValeResponse, ValeResponseAudit
from app.shared.enums import EstadoCanje
from app.shared.services.validators import (
    validator_redemption_code,
    validator_text,
)


class CanjeCreate(BaseModel):
    vale_id: UUID
    referencia: str | None = Field(default=None, max_length=255)

    @field_validator("referencia", mode="before")
    @classmethod
    def validate_referencia(cls, value: object) -> str | None:
        if value is None:
            return None
        normalized_reference = validator_text(value)
        if not normalized_reference:
            return None
        return normalized_reference

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "vale_id": "11111111-1111-4111-8111-111111111111",
                "referencia": "Solicitud desde la aplicación móvil",
            }
        },
    )


class CanjeRedeem(BaseModel):
    codigo_canje: str = Field(min_length=8, max_length=8)

    @field_validator("codigo_canje", mode="before")
    @classmethod
    def validate_codigo_canje(cls, value: object) -> str:
        return validator_redemption_code(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"codigo_canje": "00123456"}},
    )


class CanjeExpireResponse(BaseModel):
    expired_count: int = Field(ge=0)

    model_config = ConfigDict(
        json_schema_extra={"example": {"expired_count": 12}}
    )


class CanjeResponse(BaseModel):
    id: UUID
    cliente_id: UUID
    dador_id: UUID | None
    vale_id: UUID
    status: EstadoCanje
    expires_at: datetime
    codigo_canje: str
    sucursal_id: UUID | None
    total_puntos: int
    total_costo: Decimal
    referencia: str | None
    config_punto_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "33333333-3333-4333-8333-333333333333",
                "cliente_id": "44444444-4444-4444-8444-444444444444",
                "dador_id": None,
                "vale_id": "11111111-1111-4111-8111-111111111111",
                "status": "PENDIENTE",
                "expires_at": "2026-11-11T14:30:00Z",
                "codigo_canje": "00123456",
                "sucursal_id": None,
                "total_puntos": 500,
                "total_costo": "50.00",
                "referencia": "Solicitud desde la aplicación móvil",
                "config_punto_id": "66666666-6666-4666-8666-666666666666",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
            }
        },
    )


class CanjeResponseAudit(CanjeResponse):
    
    created_by: UUID | None
    
    updated_by: UUID | None
    is_deleted: bool
    deleted_at: datetime | None
    deleted_by: UUID | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "33333333-3333-4333-8333-333333333333",
                "cliente_id": "44444444-4444-4444-8444-444444444444",
                "dador_id": None,
                "vale_id": "11111111-1111-4111-8111-111111111111",
                "status": "PENDIENTE",
                "expires_at": "2026-11-11T14:30:00Z",
                "codigo_canje": "00123456",
                "sucursal_id": None,
                "total_puntos": 500,
                "total_costo": "50.00",
                "referencia": "Solicitud desde la aplicación móvil",
                "config_punto_id": "66666666-6666-4666-8666-666666666666",
                "created_at": "2026-10-12T14:30:00Z",
                "created_by": "44444444-4444-4444-8444-444444444444",
                "updated_at": "2026-10-12T14:30:00Z",
                "updated_by": "44444444-4444-4444-8444-444444444444",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )


class CanjeDetailResponse(BaseModel):
    canje: CanjeResponse
    usuario_cliente: UserResponse
    usuario_cajero_socio: UserResponse | None
    vale: ValeResponse
    sucursal: SucursalResponse | None
    negocio: NegocioResponse

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "canje": CanjeResponse.model_json_schema()["example"],
                "usuario_cliente": UserResponse.model_json_schema()["example"],
                "usuario_cajero_socio": None,
                "vale": ValeResponse.model_json_schema()["example"],
                "sucursal": None,
                "negocio": NegocioResponse.model_json_schema()["example"],
            }
        },
    )


class CanjeDetailResponseAudit(CanjeDetailResponse):
    canje: CanjeResponseAudit
    usuario_cliente: UserResponseAudit
    usuario_cajero_socio: UserResponseAudit | None
    vale: ValeResponseAudit
    sucursal: SucursalResponseAudit | None
    negocio: NegocioResponseAudit

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "canje": CanjeResponseAudit.model_json_schema()["example"],
                "usuario_cliente": UserResponseAudit.model_json_schema()["example"],
                "usuario_cajero_socio": None,
                "vale": ValeResponseAudit.model_json_schema()["example"],
                "sucursal": None,
                "negocio": NegocioResponseAudit.model_json_schema()["example"],
            }
        },
    )


class CanjeListResponse(BaseModel):
    canje: CanjeResponse
    vale: ValeResponse
    sucursal: SucursalResponse | None
    negocio: NegocioResponse

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "canje": CanjeResponse.model_json_schema()["example"],
                "vale": ValeResponse.model_json_schema()["example"],
                "sucursal": None,
                "negocio": NegocioResponse.model_json_schema()["example"],
            }
        },
    )


class CanjeListResponseAudit(CanjeListResponse):
    canje: CanjeResponseAudit
    vale: ValeResponseAudit
    sucursal: SucursalResponseAudit | None
    negocio: NegocioResponseAudit

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "canje": CanjeResponseAudit.model_json_schema()["example"],
                "vale": ValeResponseAudit.model_json_schema()["example"],
                "sucursal": None,
                "negocio": NegocioResponseAudit.model_json_schema()["example"],
            }
        },
    )
