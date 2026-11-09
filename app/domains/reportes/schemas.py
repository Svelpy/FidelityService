from datetime import date
from decimal import Decimal
from typing import ClassVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.shared.enums import Role, TipoReportePuntos


class ReportePuntosQuery(BaseModel):
    """Parámetros del reporte de puntos asignados o canjeados por periodo."""

    MAX_DIAS: ClassVar[int] = 366

    fecha_inicio: date = Field(...)
    fecha_fin: date = Field(...)
    tipo: TipoReportePuntos = Field(...)

    @model_validator(mode="after")
    def validate_rango(self) -> "ReportePuntosQuery":
        if self.fecha_fin < self.fecha_inicio:
            raise ValueError("fecha_fin debe ser igual o posterior a fecha_inicio.")
        dias = (self.fecha_fin - self.fecha_inicio).days + 1
        if dias > self.MAX_DIAS:
            raise ValueError(
                f"El rango del reporte no puede superar {self.MAX_DIAS} días."
            )
        return self

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "fecha_inicio": "2026-11-01",
                "fecha_fin": "2026-11-30",
                "tipo": "ASIGNADOS",
            }
        },
    )


class ReporteTotales(BaseModel):
    """Cantidad de registros, puntos y bolivianos acumulados."""

    cantidad: int = 0
    puntos: int = 0
    bs: Decimal = Decimal("0.00")


class ReporteSucursal(BaseModel):
    """Columna de sucursal incluida en la hoja por sucursal."""

    id: UUID
    nombre: str
    negocio_nombre: str
    eliminada: bool


class ReporteDia(BaseModel):
    """Fila diaria con los totales por sucursal y del sistema."""

    dia: date
    por_sucursal: dict[UUID, ReporteTotales]
    total: ReporteTotales


class ReporteUsuario(BaseModel):
    """Fila de la hoja por usuario con los totales del periodo."""

    id: UUID
    nombre: str
    ci: str
    role: Role
    eliminado: bool
    totales: ReporteTotales


class ReportePuntosData(BaseModel):
    """Datos consolidados del reporte, independientes del formato de salida."""

    query: ReportePuntosQuery
    sucursales: list[ReporteSucursal]
    dias: list[ReporteDia]
    total_por_sucursal: dict[UUID, ReporteTotales]
    total: ReporteTotales
    usuarios: list[ReporteUsuario]
