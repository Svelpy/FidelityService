from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class ConfigPuntos(BaseModel):
    __tablename__ = "CONFIG_PUNTOS"
    __table_args__ = {"schema": "public"}

    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, nullable=False)
    start_date: Mapped[datetime] = mapped_column(
        "Start_date",
        DateTime(timezone=False),
        nullable=False,
    )
    end_date: Mapped[datetime | None] = mapped_column(
        "End_date",
        DateTime(timezone=False),
        nullable=True,
    )
    point_voucher_factor: Mapped[float] = mapped_column(
        "Factor_punto_vale",
        DOUBLE_PRECISION,
        nullable=False,
    )
    point_operation_factor: Mapped[float] = mapped_column(
        "Factor_punto_operacion",
        DOUBLE_PRECISION,
        nullable=False,
    )
    is_operative: Mapped[bool] = mapped_column("Is_operative", Boolean, nullable=False)
