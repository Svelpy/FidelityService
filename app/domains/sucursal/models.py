from uuid import UUID

from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel


class Sucursal(BaseModel, table=True):
    __tablename__ = "sucursal"
    __table_args__ = (
        UniqueConstraint("id", "negocio_id", name="uq_sucursal_id_negocio_id"),
        Index("ix_sucursal_negocio_id", "negocio_id"),
        {"schema": "public"},
    )

    direccion: str = Field(sa_type=Text, nullable=False)
    url_ubicacion: str = Field(max_length=2048, nullable=False)
    telefono: str | None = Field(default=None, max_length=32, nullable=True)
    nombre: str = Field(max_length=160, nullable=False)
    negocio_id: UUID = Field(foreign_key="public.negocio.id", nullable=False)
