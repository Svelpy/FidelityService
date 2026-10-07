from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, Enum as SQLAlchemyEnum
from sqlalchemy import Index
from sqlmodel import Field

from app.core.base_model import BaseModel
from app.shared.enums import TipoMovimiento


class MovimientoPuntos(BaseModel, table=True):
    __tablename__ = "movimientos_puntos"
    __table_args__ = (
        CheckConstraint(
            "(" 
            "tipo_movimiento = 'ACUMULA' "
            "AND operacion_id IS NOT NULL AND canje_id IS NULL"
            ") OR ("
            "tipo_movimiento = 'CANJE' "
            "AND canje_id IS NOT NULL AND operacion_id IS NULL"
            ") OR ("
            "tipo_movimiento IN ('AJUSTE', 'EXPIRA') "
            "AND operacion_id IS NULL AND canje_id IS NULL"
            ")",
            name="ck_movimientos_puntos_referencia_por_tipo",
        ),
        Index("ix_movimientos_puntos_usuario_id", "usuario_id"),
        Index("ix_movimientos_puntos_operacion_id", "operacion_id"),
        Index("ix_movimientos_puntos_canje_id", "canje_id"),
        {"schema": "public"},
    )

    usuario_id: UUID = Field(foreign_key="public.usuario.id", nullable=False)
    tipo_movimiento: TipoMovimiento = Field(
        sa_type=SQLAlchemyEnum(
            TipoMovimiento,
            name="tipo_movimiento",
            schema="public",
            native_enum=True,
        ),
        nullable=False,
    )
    puntos: int = Field(sa_type=BigInteger, nullable=False)
    operacion_id: UUID | None = Field(
        default=None,
        foreign_key="public.operacion.id",
        nullable=True,
    )
    canje_id: UUID | None = Field(
        default=None,
        foreign_key="public.canje.id",
        nullable=True,
    )
