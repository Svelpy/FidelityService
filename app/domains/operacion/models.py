from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Numeric, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class Operacion(BaseModel, table=True):
    __tablename__ = "operacion"
    __table_args__ = (
        CheckConstraint(
            "emisor_id <> receptor_id",
            name="ck_operacion_emisor_receptor_diferentes",
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
    config_punto_id: UUID = Field(
        foreign_key="public.config_puntos.id",
        nullable=False,
    )
    sucursal_id: UUID = Field(foreign_key="public.sucursal.id", nullable=False)
    referencia: str | None = Field(default=None, sa_type=Text, nullable=True)
