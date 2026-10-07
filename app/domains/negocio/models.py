from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import TipoNegocio


class Negocio(BaseModel, table=True):
    __tablename__ = "negocio"
    __table_args__ = (
        UniqueConstraint("id", "tipo", name="uq_negocio_id_tipo"),
        Index("ix_negocio_nombre", "nombre"),
        Index("ix_negocio_tipo", "tipo"),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=160, nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
    telefono: str | None = Field(default=None, max_length=32, nullable=True)
    imagen_url: str | None = Field(default=None, max_length=2048, nullable=True)
    tipo: TipoNegocio = Field(
        sa_type=SQLAlchemyEnum(
            TipoNegocio,
            name="tipo_negocio",
            schema="public",
            native_enum=True,
        ),
        nullable=False,
    )
