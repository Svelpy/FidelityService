from uuid import UUID

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Vale(BaseModel):
    __tablename__ = "VALE"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    total_points: Mapped[int] = mapped_column("Total_puntos", Integer, nullable=False)
    name: Mapped[str] = mapped_column("Nombre", String, nullable=False)
    description: Mapped[str | None] = mapped_column("Descripcion", Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column("Imagen_url", String, nullable=True)
    likes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_value: Mapped[float] = mapped_column("Total_vale", DOUBLE_PRECISION, nullable=False)
    config_id: Mapped[UUID] = mapped_column(
        "Config_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.CONFIG_PUNTOS.id",
            name="fk_VALE_Config_id_CONFIG_PUNTOS_id",
        ),
        nullable=False,
    )
