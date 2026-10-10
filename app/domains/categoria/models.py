from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel


class Categoria(BaseModel, table=True):
    __tablename__ = "categoria"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_categoria_slug"),
        Index("ix_categoria_nombre", "nombre"),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=60, nullable=False)
    slug: str = Field(max_length=255, nullable=False)
    icon_number: int = Field(nullable=False)
    descripcion: str | None = Field(default=None, sa_type=Text, nullable=True)
