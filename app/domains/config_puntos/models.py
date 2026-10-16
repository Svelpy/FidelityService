from datetime import datetime
from sqlalchemy import BigInteger, CheckConstraint, DateTime, Enum as SQLAlchemyEnum
from sqlalchemy import Index, text
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import EstadoConfigPuntos


class ConfigPuntos(BaseModel, table=True):
    __tablename__ = "config_puntos"
    __table_args__ = (
        CheckConstraint(
            "asignacion_bolivianos > 0 AND asignacion_puntos > 0",
            name="ck_config_puntos_asignacion_positiva",
        ),
        CheckConstraint(
            "costo_vale_bolivianos > 0 AND costo_vale_puntos > 0",
            name="ck_config_puntos_costo_vale_positivo",
        ),
        CheckConstraint(
            "(status = 'ACTIVE' AND end_date IS NULL) OR "
            "(status = 'INACTIVE' AND end_date > start_date)",
            name="ck_config_puntos_rango_fechas",
        ),
        Index(
            "uq_config_puntos_activa",
            text("(true)"),
            unique=True,
            postgresql_where=text("status = 'ACTIVE' AND is_deleted = false"),
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
    asignacion_bolivianos: int = Field(
        sa_type=BigInteger,
        nullable=False,
    )
    asignacion_puntos: int = Field(
        sa_type=BigInteger,
        nullable=False,
    )
    costo_vale_bolivianos: int = Field(
        sa_type=BigInteger,
        nullable=False,
    )
    costo_vale_puntos: int = Field(
        sa_type=BigInteger,
        nullable=False,
    )
    status: EstadoConfigPuntos = Field(
        default=EstadoConfigPuntos.ACTIVE,
        sa_type=SQLAlchemyEnum(
            EstadoConfigPuntos,
            name="estado_config_puntos",
            native_enum=False,
            create_constraint=True,
        ),
        nullable=False,
    )
