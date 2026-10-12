from uuid import UUID

from sqlalchemy import Index, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel


class Sucursal(BaseModel, table=True):
    __tablename__ = "sucursal"
    __table_args__ = (
        UniqueConstraint("id", "negocio_id", name="uq_sucursal_id_negocio_id"),
        Index("ix_sucursal_negocio_id", "negocio_id"),
        {"schema": "public"},
    )

    direccion: str | None = Field(default=None, max_length=255, nullable=True)
    url_ubicacion: str | None = Field(default=None, max_length=2048, nullable=True)
    telefono: str | None = Field(default=None, max_length=20, nullable=True)
    nombre: str = Field(max_length=60, nullable=False)
    negocio_id: UUID = Field(foreign_key="public.negocio.id", nullable=False)
