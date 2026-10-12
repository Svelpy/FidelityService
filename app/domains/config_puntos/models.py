from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Index, Numeric, text
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
        Index(
            "uq_config_puntos_activa",
            text("(true)"),
            unique=True,
            postgresql_where=text("end_date IS NULL AND is_deleted = false"),
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
