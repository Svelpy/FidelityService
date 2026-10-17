from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domains.categoria.schemas import CategoriaResponse, CategoriaResponseAudit
from app.domains.negocio.schemas import NegocioResponse, NegocioResponseAudit
from app.domains.sucursal.schemas import SucursalResponse, SucursalResponseAudit
from app.shared.services.validators import (
    validator_non_empty_text,
    validator_positive_integer,
    validator_positive_money,
)


class ValeCreate(BaseModel):
    total_costo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    total_puntos: int = Field(gt=0, le=2_147_483_647, strict=True)
    nombre: str = Field(min_length=1, max_length=60)
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    categoria_id: UUID = Field(...)
    negocio_id: UUID = Field(...)

    @field_validator("total_costo", mode="before")
    @classmethod
    def validate_total_costo(cls, value: object) -> Decimal:
        return validator_positive_money(value)

    @field_validator("total_puntos", mode="before")
    @classmethod
    def validate_total_puntos(cls, value: object) -> int:
        return validator_positive_integer(value)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        return validator_non_empty_text(value)

    @field_validator("descripcion", mode="before")
    @classmethod
    def validate_descripcion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "total_costo": "50.00",
                "total_puntos": 500,
                "nombre": "Vale de consumo Bs 50",
                "descripcion": "Canjeable por productos seleccionados.",
                "categoria_id": "11111111-1111-4111-8111-111111111111",
                "negocio_id": "22222222-2222-4222-8222-222222222222",
            }
        },
    )


class ValeUpdate(BaseModel):
    total_costo: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    total_puntos: int | None = Field(default=None, gt=0, le=2_147_483_647, strict=True)
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    categoria_id: UUID | None = Field(default=None)
    negocio_id: UUID | None = Field(default=None)

    @field_validator("total_costo", mode="before")
    @classmethod
    def validate_total_costo(cls, value: object) -> Decimal:
        if value is None:
            raise ValueError("El costo total no puede ser null.")
        return validator_positive_money(value)

    @field_validator("total_puntos", mode="before")
    @classmethod
    def validate_total_puntos(cls, value: object) -> int:
        if value is None:
            raise ValueError("El total de puntos no puede ser null.")
        return validator_positive_integer(value)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_non_empty_text(value)

    @field_validator("descripcion", mode="before")
    @classmethod
    def validate_descripcion(cls, value: object) -> str | None:
        if value is None:
            return None
        return validator_non_empty_text(value)

    @field_validator("categoria_id", "negocio_id")
    @classmethod
    def validate_required_uuid(cls, value: UUID | None) -> UUID:
        if value is None:
            raise ValueError("El identificador no puede ser null.")
        return value

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "total_costo": "55.00",
                "total_puntos": 550,
                "nombre": "Vale de consumo Bs 55",
                "descripcion": None,
                "categoria_id": "11111111-1111-4111-8111-111111111111",
                "negocio_id": "22222222-2222-4222-8222-222222222222",
            }
        },
    )

class ValeResponse(BaseModel):
    id: UUID
    total_costo: Decimal
    total_puntos: int
    nombre: str
    descripcion: str | None
    image_url: str | None
    categoria_id: UUID
    negocio_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "33333333-3333-4333-8333-333333333333",
                "total_costo": "50.00",
                "total_puntos": 500,
                "nombre": "Vale de consumo Bs 50",
                "descripcion": "Canjeable por productos seleccionados.",
                "image_url": None,
                "categoria_id": "11111111-1111-4111-8111-111111111111",
                "negocio_id": "22222222-2222-4222-8222-222222222222",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
            }
        },
    )


class ValeResponseAudit(ValeResponse):

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
                "total_costo": "50.00",
                "total_puntos": 500,
                "nombre": "Vale de consumo Bs 50",
                "descripcion": "Canjeable por productos seleccionados.",
                "image_url": None,
                "categoria_id": "11111111-1111-4111-8111-111111111111",
                "negocio_id": "22222222-2222-4222-8222-222222222222",
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


class ValeListResponse(BaseModel):
    vale: ValeResponse
    negocio: NegocioResponse
    categoria: CategoriaResponse

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "vale": ValeResponse.model_json_schema()["example"],
                "negocio": NegocioResponse.model_json_schema()["example"],
                "categoria": CategoriaResponse.model_json_schema()["example"],
            }
        },
    )


class ValeListResponseAudit(ValeListResponse):
    vale: ValeResponseAudit
    negocio: NegocioResponseAudit
    categoria: CategoriaResponseAudit

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "vale": ValeResponseAudit.model_json_schema()["example"],
                "negocio": NegocioResponseAudit.model_json_schema()["example"],
                "categoria": CategoriaResponseAudit.model_json_schema()["example"],
            }
        },
    )


class ValeDetailResponse(BaseModel):
    vale: ValeResponse
    categoria: CategoriaResponse
    negocio: NegocioResponse
    sucursales: list[SucursalResponse]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "vale": ValeResponse.model_json_schema()["example"],
                "categoria": CategoriaResponse.model_json_schema()["example"],
                "negocio": NegocioResponse.model_json_schema()["example"],
                "sucursales": [
                    SucursalResponse.model_json_schema()["example"]
                ],
            }
        },
    )


class ValeDetailResponseAudit(ValeDetailResponse):
    vale: ValeResponseAudit
    categoria: CategoriaResponseAudit
    negocio: NegocioResponseAudit
    sucursales: list[SucursalResponseAudit]

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "vale": ValeResponseAudit.model_json_schema()["example"],
                "categoria": CategoriaResponseAudit.model_json_schema()["example"],
                "negocio": NegocioResponseAudit.model_json_schema()["example"],
                "sucursales": [
                    SucursalResponseAudit.model_json_schema()["example"]
                ],
            }
        },
    )


class ValePuntosSuggestionRequest(BaseModel):
    total_costo: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @field_validator("total_costo", mode="before")
    @classmethod
    def validate_total_costo(cls, value: object) -> Decimal:
        return validator_positive_money(value)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={"example": {"total_costo": "50.00"}},
    )


class ValePuntosSuggestionResponse(BaseModel):
    puntos_sugeridos: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"puntos_sugeridos": 500}}
    )
