from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric
from sqlmodel import Field

from app.core.base_model import BaseModel


class Operacion(BaseModel, table=True):
    __tablename__ = "operacion"
    __table_args__ = (
        CheckConstraint(
            "emisor_id <> receptor_id",
            name="ck_operacion_emisor_receptor_diferentes",
        ),
        CheckConstraint(
            "total_compra > 0",
            name="ck_operacion_total_compra_positivo",
        ),
        CheckConstraint(
            "total_puntos > 0",
            name="ck_operacion_total_puntos_positivo",
        ),
        CheckConstraint(
            "(anulada_at IS NULL AND anulada_por IS NULL "
            "AND motivo_anulacion IS NULL) OR "
            "(anulada_at IS NOT NULL AND anulada_por IS NOT NULL "
            "AND motivo_anulacion IS NOT NULL)",
            name="ck_operacion_anulacion_consistente",
        ),
        Index("ix_operacion_emisor_id", "emisor_id"),
        Index("ix_operacion_receptor_id", "receptor_id"),
        Index("ix_operacion_sucursal_id", "sucursal_id"),
        Index("ix_operacion_config_punto_id", "config_punto_id"),
        {"schema": "public"},
    )

    receptor_id: UUID = Field(foreign_key="public.usuario.id", nullable=False)
    emisor_id: UUID = Field(foreign_key="public.usuario.id", nullable=False)
    total_compra: Decimal = Field(sa_type=Numeric(14, 2), nullable=False)
    total_puntos: int = Field(nullable=False)
    config_punto_id: UUID = Field(foreign_key="public.config_puntos.id", nullable=False)
    sucursal_id: UUID = Field(foreign_key="public.sucursal.id", nullable=False)
    referencia: str | None = Field(default=None, max_length=255, nullable=True)
    anulada_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    anulada_por: UUID | None = Field(
        default=None,
        foreign_key="public.usuario.id",
        nullable=True,
    )
    motivo_anulacion: str | None = Field(default=None, max_length=255, nullable=True)
