from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FactorPuntosInput(BaseModel):
    cant_bs: int = Field(gt=0, strict=True)
    cant_puntos: int = Field(gt=0, strict=True)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "cant_bs": 100,
                "cant_puntos": 10,
            }
        },
    )


class ConfigPuntosCreate(BaseModel):
    asignacion: FactorPuntosInput
    costo_vale: FactorPuntosInput

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "asignacion": {
                    "cant_bs": 100,
                    "cant_puntos": 10,
                },
                "costo_vale": {
                    "cant_bs": 50,
                    "cant_puntos": 500,
                },
            }
        },
    )


class ConfigPuntosResponse(BaseModel):
    id: UUID
    start_date: datetime
    end_date: datetime | None
    factor_asignacion_puntos: Decimal
    factor_costo_vale: Decimal
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "start_date": "2026-10-12T14:30:00Z",
                "end_date": None,
                "factor_asignacion_puntos": "0.100000",
                "factor_costo_vale": "10.000000",
            }
        },
    )


class ConfigPuntosResponseAudit(ConfigPuntosResponse):

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
                "start_date": "2026-10-12T14:30:00Z",
                "end_date": None,
                "factor_asignacion_puntos": "0.100000",
                "factor_costo_vale": "10.000000",
                "created_at": "2026-10-12T14:30:00Z",
                "created_by": "22222222-2222-4222-8222-222222222222",
                "updated_at": "2026-10-12T14:30:00Z",
                "updated_by": "22222222-2222-4222-8222-222222222222",
                "is_deleted": False,
                "deleted_at": None,
                "deleted_by": None,
            }
        },
    )
