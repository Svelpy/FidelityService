from datetime import date
from uuid import UUID

from sqlalchemy import CheckConstraint, Enum as SQLAlchemyEnum
from sqlalchemy import Index, Text, UniqueConstraint
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import Role


class User(BaseModel, table=True):
    __tablename__ = "usuario"
    __table_args__ = (
        UniqueConstraint("ci", name="uq_usuario_ci"),
        CheckConstraint("puntos >= 0", name="ck_usuario_puntos_no_negativos"),
        Index("ix_usuario_sucursal_id", "sucursal_id"),
        Index("ix_usuario_role", "role"),
        {"schema": "public"},
    )

    nombre: str = Field(max_length=120, nullable=False)
    apellidos: str = Field(max_length=160, nullable=False)
    telefono: str = Field(max_length=32, nullable=False)
    email: str | None = Field(default=None, max_length=320, nullable=True)
    birth_date: date | None = Field(default=None, nullable=True)
    ci: str = Field(max_length=32, nullable=False)
    direccion: str | None = Field(default=None, sa_type=Text, nullable=True)
    avatar_url: str | None = Field(default=None, max_length=2048, nullable=True)
    genero: str | None = Field(default=None, max_length=1, nullable=True)
    role: Role = Field(
        sa_type=SQLAlchemyEnum(
            Role,
            name="role_usuario",
            native_enum=False,
            create_constraint=True,
            length=20,
        ),
        nullable=False,
    )
    puntos: int = Field(default=0, nullable=False)
    sucursal_id: UUID | None = Field(
        default=None,
        foreign_key="public.sucursal.id",
        nullable=True,
    )
    password_hash: str = Field(max_length=255, nullable=False)
