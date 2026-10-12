from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Index, Numeric, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel


class Vale(BaseModel, table=True):
    __tablename__ = "vale"
    __table_args__ = (
        UniqueConstraint("id", "negocio_id", name="uq_vale_id_negocio_id"),
        CheckConstraint("total_costo > 0", name="ck_vale_total_costo_positivo"),
        CheckConstraint("total_puntos > 0", name="ck_vale_total_puntos_positivo"),
        Index("ix_vale_nombre", "nombre"),
        Index("ix_vale_categoria_id", "categoria_id"),
        Index("ix_vale_negocio_id", "negocio_id"),
        {"schema": "public"},
    )

    total_costo: Decimal = Field(sa_type=Numeric(14, 2), nullable=False)
    total_puntos: int = Field(nullable=False)
    nombre: str = Field(max_length=60, nullable=False)
    descripcion: str | None = Field(default=None, max_length=255, nullable=True)
    image_url: str | None = Field(default=None, max_length=2048, nullable=True)
    categoria_id: UUID = Field(foreign_key="public.categoria.id", nullable=False)
    negocio_id: UUID = Field(foreign_key="public.negocio.id", nullable=False)
