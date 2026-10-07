from decimal import Decimal
from uuid import UUID

from sqlalchemy import Index, Numeric, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel


class Vale(BaseModel, table=True):
    __tablename__ = "vale"
    __table_args__ = (
        UniqueConstraint("id", "negocio_id", name="uq_vale_id_negocio_id"),
        Index("ix_vale_categoria_id", "categoria_id"),
        Index("ix_vale_negocio_id", "negocio_id"),
        {"schema": "public"},
    )

    total_puntos: int = Field(nullable=False)
    nombre: str = Field(max_length=160, nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
    imagen_url: str | None = Field(default=None, max_length=2048, nullable=True)
    total_costo: Decimal = Field(sa_type=Numeric(14, 2), nullable=False)
    categoria_id: UUID = Field(
        foreign_key="public.categoria.id",
        nullable=False,
    )
    negocio_id: UUID = Field(foreign_key="public.negocio.id", nullable=False)
