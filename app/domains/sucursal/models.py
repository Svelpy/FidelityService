from uuid import UUID

from sqlalchemy import String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Sucursal(BaseModel):
    __tablename__ = "SUCURSAL"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    name: Mapped[str] = mapped_column("Nombre", String, nullable=False)
    description: Mapped[str | None] = mapped_column("Descripcion", Text, nullable=True)
    address: Mapped[str] = mapped_column("Direccion", Text, nullable=False)
    location_url: Mapped[str | None] = mapped_column("Url_ubicacion", String, nullable=True)
    phone: Mapped[str | None] = mapped_column("Telefono", String, nullable=True)
    image_url: Mapped[str | None] = mapped_column("imagen_url", String, nullable=True)
