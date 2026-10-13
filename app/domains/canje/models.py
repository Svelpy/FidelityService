from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import EstadoCanje


class Canje(BaseModel, table=True):
    __tablename__ = "canje"
    __table_args__ = (
        UniqueConstraint("codigo_canje", name="uq_canje_codigo_canje"),
        CheckConstraint(
            "codigo_canje ~ '^[0-9]{8}$'",
            name="ck_canje_codigo_ocho_digitos",
        ),
        CheckConstraint(
            "total_puntos > 0",
            name="ck_canje_total_puntos_positivo",
        ),
        CheckConstraint(
            "total_costo > 0",
            name="ck_canje_total_costo_positivo",
        ),
        CheckConstraint(
            "expires_at > created_at",
            name="ck_canje_expiracion_posterior_creacion",
        ),
        CheckConstraint(
            "dador_id IS NULL OR dador_id <> cliente_id",
            name="ck_canje_cliente_dador_diferentes",
        ),
        CheckConstraint(
            "(status = 'CANJEADO' AND dador_id IS NOT NULL "
            "AND sucursal_id IS NOT NULL) OR "
            "(status IN ('PENDIENTE', 'EXPIRADO', 'CANCELADO') "
            "AND dador_id IS NULL AND sucursal_id IS NULL)",
            name="ck_canje_dador_sucursal_segun_estado",
        ),
        Index("ix_canje_cliente_id", "cliente_id"),
        Index("ix_canje_dador_id", "dador_id"),
        Index("ix_canje_vale_id", "vale_id"),
        Index("ix_canje_sucursal_id", "sucursal_id"),
        Index("ix_canje_config_punto_id", "config_punto_id"),
        Index("ix_canje_status", "status"),
        {"schema": "public"},
    )

    cliente_id: UUID = Field(foreign_key="public.usuario.id", nullable=False)
    dador_id: UUID | None = Field(default=None,foreign_key="public.usuario.id",nullable=True)
    vale_id: UUID = Field(foreign_key="public.vale.id", nullable=False)
    status: EstadoCanje = Field(default=EstadoCanje.PENDIENTE,sa_type=SQLAlchemyEnum(EstadoCanje,name="estado_canje",schema="public",native_enum=True),nullable=False)
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
    codigo_canje: str = Field(sa_type=String(8), nullable=False)
    sucursal_id: UUID | None = Field(default=None,foreign_key="public.sucursal.id",nullable=True)
    total_puntos: int = Field(nullable=False)
    total_costo: Decimal = Field(sa_type=Numeric(14, 2), nullable=False)
    referencia: str | None = Field(default=None, max_length=255, nullable=True)
    config_punto_id: UUID = Field(foreign_key="public.config_puntos.id",nullable=False)
