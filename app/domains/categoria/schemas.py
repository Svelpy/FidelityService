from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.services.validators import (
    validator_non_empty_text,
    validator_non_negative_integer,
    validator_slug_source,
)


class CategoriaCreate(BaseModel):
    nombre: str = Field(...,min_length=1, max_length=60)
    icon_number: int = Field(default=0,ge=0)
    descripcion: str | None = Field(default=None,min_length=1, max_length=255)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_slug_source(value)

    @field_validator("icon_number", mode="before")
    @classmethod
    def validate_icon_number(cls, value: object) -> int:
        if value is None:
            raise ValueError("El número de icono no puede ser null.")
        return validator_non_negative_integer(value)

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
                "nombre": "Gastronomía",
                "icon_number": 3,
                "descripcion": "Vales para restaurantes y cafeterías.",
            }
        },
    )


class CategoriaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=60)
    icon_number: int | None = Field(default=None, ge=0)
    descripcion: str | None = Field(default=None,min_length=1, max_length=255)

    @field_validator("nombre", mode="before")
    @classmethod
    def validate_nombre(cls, value: object) -> str:
        if value is None:
            raise ValueError("El nombre no puede ser null.")
        return validator_slug_source(value)

    @field_validator("icon_number", mode="before")
    @classmethod
    def validate_icon_number(cls, value: object) -> int:
        if value is None:
            raise ValueError("El número de icono no puede ser null.")
        return validator_non_negative_integer(value)

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
                "nombre": "Gastronomía y bebidas",
                "icon_number": 4,
                "descripcion": None,
            }
        },
    )


class CategoriaResponse(BaseModel):
    id: UUID
    nombre: str
    slug: str
    icon_number: int
    descripcion: str | None

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "nombre": "Gastronomía",
                "slug": "gastronomia",
                "icon_number": 3,
                "descripcion": "Vales para restaurantes y cafeterías.",
            }
        },
    )


class CategoriaResponseAudit(CategoriaResponse):
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
                "nombre": "Gastronomía",
                "slug": "gastronomia",
                "icon_number": 3,
                "descripcion": "Vales para restaurantes y cafeterías.",
                "created_at": "2026-10-10T14:30:00Z",
                "created_by": "22222222-2222-4222-8222-222222222222",
                "updated_at": "2026-10-10T15:00:00Z",
                "updated_by": "22222222-2222-4222-8222-222222222222",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
