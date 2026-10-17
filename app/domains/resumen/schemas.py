from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.shared.enums import NivelCliente


class NivelClienteResponse(BaseModel):
    actual: NivelCliente
    puntos_min: int
    puntos_max: int | None
    siguiente: NivelCliente | None
    puntos_para_siguiente: int | None
    progreso: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "actual": "PLATA",
                "puntos_min": 501,
                "puntos_max": 1000,
                "siguiente": "ORO",
                "puntos_para_siguiente": 251,
                "progreso": 49,
            }
        },
    )


class ResumenClienteResponse(BaseModel):
    nombre: str
    puntos: int
    nivel: NivelClienteResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre": "Ana",
                "puntos": 750,
                "nivel": NivelClienteResponse.model_json_schema()["example"],
            }
        },
    )


class ResumenOperacionesResponse(BaseModel):
    cantidad: int
    total_compra: Decimal
    puntos_otorgados: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "cantidad": 12,
                "total_compra": "1450.50",
                "puntos_otorgados": 145,
            }
        },
    )


class ResumenOperacionesPeriodoResponse(BaseModel):
    hoy: ResumenOperacionesResponse
    mes: ResumenOperacionesResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "hoy": ResumenOperacionesResponse.model_json_schema()["example"],
                "mes": {
                    "cantidad": 310,
                    "total_compra": "38420.00",
                    "puntos_otorgados": 3842,
                },
            }
        },
    )


class ResumenClientesResponse(BaseModel):
    total: int
    nuevos_mes: int
    puntos_en_circulacion: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 820,
                "nuevos_mes": 37,
                "puntos_en_circulacion": 152300,
            }
        },
    )


class ResumenCanjesCantidadResponse(BaseModel):
    cantidad: int
    puntos: int

    model_config = ConfigDict(
        json_schema_extra={"example": {"cantidad": 4, "puntos": 2000}},
    )


class ResumenCanjesResponse(BaseModel):
    pendientes: int
    hoy: ResumenCanjesCantidadResponse
    mes: ResumenCanjesCantidadResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pendientes": 18,
                "hoy": ResumenCanjesCantidadResponse.model_json_schema()["example"],
                "mes": {"cantidad": 95, "puntos": 47500},
            }
        },
    )


class ResumenTopValeResponse(BaseModel):
    vale_id: UUID
    nombre: str
    negocio: str
    canjes: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "vale_id": "33333333-3333-4333-8333-333333333333",
                "nombre": "Vale de consumo Bs 50",
                "negocio": "Café Central",
                "canjes": 27,
            }
        },
    )


class ResumenAdminResponse(BaseModel):
    fecha: date
    clientes: ResumenClientesResponse
    operaciones: ResumenOperacionesPeriodoResponse
    canjes: ResumenCanjesResponse
    top_vales_mes: list[ResumenTopValeResponse]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fecha": "2026-10-17",
                "clientes": ResumenClientesResponse.model_json_schema()["example"],
                "operaciones": (
                    ResumenOperacionesPeriodoResponse.model_json_schema()["example"]
                ),
                "canjes": ResumenCanjesResponse.model_json_schema()["example"],
                "top_vales_mes": [
                    ResumenTopValeResponse.model_json_schema()["example"]
                ],
            }
        },
    )


class ResumenCajeroResponse(BaseModel):
    fecha: date
    operaciones_hoy: ResumenOperacionesResponse

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fecha": "2026-10-17",
                "operaciones_hoy": (
                    ResumenOperacionesResponse.model_json_schema()["example"]
                ),
            }
        },
    )
