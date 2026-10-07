from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric
from sqlmodel import Field

from app.core.base_model import BaseModel


class ConfigPuntos(BaseModel, table=True):
    __tablename__ = "config_puntos"
    __table_args__ = (
        CheckConstraint(
            "factor_asignacion_puntos > 0",
            name="ck_config_puntos_factor_asignacion_positivo",
        ),
        CheckConstraint(
            "factor_costo_vale > 0",
            name="ck_config_puntos_factor_costo_positivo",
        ),
        CheckConstraint(
            "end_date IS NULL OR end_date > start_date",
            name="ck_config_puntos_rango_fechas",
        ),
        {"schema": "public"},
    )

    start_date: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    end_date: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    factor_asignacion_puntos: Decimal = Field(
        sa_type=Numeric(18, 6),
        nullable=False,
    )
    factor_costo_vale: Decimal = Field(
        sa_type=Numeric(18, 6),
        nullable=False,
    )
