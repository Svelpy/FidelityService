from sqlalchemy import Enum as SQLAlchemyEnum
from sqlalchemy import Index, UniqueConstraint, text
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import TipoNegocio


class Negocio(BaseModel, table=True):
    __tablename__ = "negocio"
    __table_args__ = (
        UniqueConstraint("id", "tipo", name="uq_negocio_id_tipo"),
        Index("ix_negocio_nombre", "nombre"),
        Index("ix_negocio_tipo", "tipo"),
        Index(
            "uq_negocio_nombre_activo_ci",
            text("lower(nombre)"),
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index(
            "uq_negocio_main_activo",
            "tipo",
            unique=True,
            postgresql_where=text(
                "tipo = 'MAIN' AND is_deleted = false"
            ),
        ),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=60, nullable=False)
    descripcion: str | None = Field(default=None, max_length=255, nullable=True)
    telefono: str | None = Field(default=None, max_length=20, nullable=True)
    image_url: str | None = Field(default=None, max_length=2048, nullable=True)
    tipo: TipoNegocio = Field(
        sa_type=SQLAlchemyEnum(
            TipoNegocio,
            name="tipo_negocio",
            schema="public",
            native_enum=True,
        ),
        nullable=False,
    )
