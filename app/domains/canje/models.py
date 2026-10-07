from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
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
            "codigo_canje ~ '^[0-9]{6}$'",
            name="ck_canje_codigo_seis_digitos",
        ),
        ForeignKeyConstraint(
            ["vale_id", "negocio_id"],
            ["public.vale.id", "public.vale.negocio_id"],
            name="fk_canje_vale_negocio",
        ),
        ForeignKeyConstraint(
            ["sucursal_id", "negocio_id"],
            ["public.sucursal.id", "public.sucursal.negocio_id"],
            name="fk_canje_sucursal_negocio",
        ),
        Index("ix_canje_cliente_id", "cliente_id"),
        Index("ix_canje_dador_id", "dador_id"),
        Index("ix_canje_vale_id", "vale_id"),
        Index("ix_canje_sucursal_id", "sucursal_id"),
        Index("ix_canje_negocio_id", "negocio_id"),
        Index("ix_canje_config_punto_id", "config_punto_id"),
        Index("ix_canje_status", "status"),
        {"schema": "public"},
    )

    cliente_id: UUID = Field(foreign_key="public.usuario.id", nullable=False)
    dador_id: UUID | None = Field(
        default=None,
        foreign_key="public.usuario.id",
        nullable=True,
    )
    vale_id: UUID = Field(nullable=False)
    status: EstadoCanje = Field(
        default=EstadoCanje.PENDIENTE,
        sa_type=SQLAlchemyEnum(
            EstadoCanje,
            name="estado_canje",
            schema="public",
            native_enum=True,
        ),
        nullable=False,
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    codigo_canje: str = Field(sa_type=String(6), nullable=False)
    sucursal_id: UUID = Field(nullable=False)
    negocio_id: UUID = Field(nullable=False)
    total_puntos: int = Field(nullable=False)
    total_costo: Decimal = Field(sa_type=Numeric(14, 2), nullable=False)
    referencia: str | None = Field(default=None, sa_type=Text, nullable=True)
    config_punto_id: UUID = Field(
        foreign_key="public.config_puntos.id",
        nullable=False,
    )
