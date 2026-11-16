from sqlalchemy import Index, Text, text
from sqlmodel import Field

from app.core.base_model import BaseModel


class Categoria(BaseModel, table=True):
    __tablename__ = "categoria"
    __table_args__ = (
        # Único solo entre categorías activas: una eliminada libera su slug.
        Index(
            "uq_categoria_slug",
            "slug",
            unique=True,
            postgresql_where=text("is_deleted = false"),
        ),
        Index("ix_categoria_nombre", "nombre"),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=60, nullable=False)
    slug: str = Field(max_length=255, nullable=False)
    icon_number: int = Field(nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
