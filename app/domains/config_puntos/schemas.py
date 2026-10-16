from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.shared.enums import EstadoConfigPuntos


class ConversionPuntosInput(BaseModel):
    bolivianos: int = Field(gt=0, le=9_223_372_036_854_775_807, strict=True)
    puntos: int = Field(gt=0, le=9_223_372_036_854_775_807, strict=True)

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "bolivianos": 100,
                "puntos": 10,
            }
        },
    )


class ConfigPuntosCreate(BaseModel):
    asignacion: ConversionPuntosInput
    costo_vale: ConversionPuntosInput

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "asignacion": {
                    "bolivianos": 100,
                    "puntos": 10,
                },
                "costo_vale": {
                    "bolivianos": 50,
                    "puntos": 500,
                },
            }
        },
    )


class ConfigPuntosResponse(BaseModel):
    id: UUID
    start_date: datetime
    end_date: datetime | None
    asignacion_bolivianos: int
    asignacion_puntos: int
    costo_vale_bolivianos: int
    costo_vale_puntos: int
    status: EstadoConfigPuntos
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "11111111-1111-4111-8111-111111111111",
                "start_date": "2026-10-12T14:30:00Z",
                "end_date": None,
                "asignacion_bolivianos": 100,
                "asignacion_puntos": 10,
                "costo_vale_bolivianos": 50,
                "costo_vale_puntos": 500,
                "status": "ACTIVE",
                "created_at": "2026-10-12T14:30:00Z",
                "updated_at": "2026-10-12T14:30:00Z",
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
                "asignacion_bolivianos": 100,
                "asignacion_puntos": 10,
                "costo_vale_bolivianos": 50,
                "costo_vale_puntos": 500,
                "status": "ACTIVE",
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
