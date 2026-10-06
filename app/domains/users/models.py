from uuid import UUID

from sqlalchemy import BigInteger, Enum as SQLAlchemyEnum, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel
from app.shared.enums import Role


class User(BaseModel):
    __tablename__ = "USUARIO"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column("Nombre", String, nullable=False)
    lastname: Mapped[str] = mapped_column("Apellidos", String, nullable=False)
    phone_number: Mapped[str] = mapped_column("Telefono", String, nullable=False)
    email: Mapped[str | None] = mapped_column("Correo", String, nullable=True)
    birth_date: Mapped[int | None] = mapped_column("Birdate", BigInteger, nullable=True)
    ci: Mapped[str] = mapped_column("CI", String, nullable=False)
    address: Mapped[str | None] = mapped_column("Direccion", Text, nullable=True)
    avatar_url: Mapped[str | None] = mapped_column("Avatar_url", String, nullable=True)
    gender: Mapped[str | None] = mapped_column("Genero", String, nullable=True)
    role: Mapped[Role] = mapped_column("Role", SQLAlchemyEnum(Role, native_enum=False, create_constraint=False, length=20), nullable=False,)
    password_hash: Mapped[str] = mapped_column("password_hash", String, nullable=False)
    points: Mapped[int] = mapped_column("Puntos", BigInteger, nullable=False)

    def __repr__(self) -> str:
        return f"<User id={self.id}>"
