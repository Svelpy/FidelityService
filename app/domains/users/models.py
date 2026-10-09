from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum as SQLAlchemyEnum
from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import Role, Genero


class User(BaseModel, table=True):
    __tablename__ = "usuario"
    __table_args__ = (
        UniqueConstraint("ci", name="uq_usuario_ci"),
        UniqueConstraint("email", name="uq_usuario_email"),
        CheckConstraint("puntos >= 0", name="ck_usuario_puntos_no_negativos"),
        Index("ix_usuario_sucursal_id", "sucursal_id"),
        Index("ix_usuario_role", "role"),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=60, nullable=False)
    ci: str = Field(max_length=20, nullable=False)
    telefono: str = Field(max_length=20, nullable=False)

    role: Role = Field(
        sa_type=SQLAlchemyEnum(Role, name="role_usuario",native_enum=False,create_constraint=True),
        nullable=False
        )
    genero: Genero= Field(
        sa_type=SQLAlchemyEnum(Genero, name="genero_usuario",native_enum=False,create_constraint=True),
        nullable=False
        )
    puntos: int = Field(default=0, nullable=False)
    password_hash: str = Field(max_length=255, nullable=False) # sera su telefono celular

    apellidos: str | None= Field(default=None,max_length=120, nullable=True)
    email: str | None = Field(default=None, max_length=320, nullable=True)
    birth_date: date | None = Field(default=None, nullable=True)
    direccion: str | None = Field(default=None, max_length=120, nullable=True)
    avatar_url: str | None = Field(default=None, max_length=2048, nullable=True)
    sucursal_id: UUID | None = Field(default=None,foreign_key="public.sucursal.id",nullable=True)
