from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import DOUBLE_PRECISION, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Operacion(BaseModel):
    __tablename__ = "OPERACION"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    receptor_id: Mapped[UUID] = mapped_column(
        "Receptor_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.USUARIO.id",
            name="fk_OPERACION_Receptor_id_USUARIO_id",
        ),
        nullable=False,
    )
    issuer_id: Mapped[UUID] = mapped_column(
        "Emisor_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.USUARIO.id",
            name="fk_OPERACION_Emisor_id_USUARIO_id",
        ),
        nullable=False,
    )
    total_purchase: Mapped[float] = mapped_column(
        "Total_compra",
        DOUBLE_PRECISION,
        nullable=False,
    )
    total_points: Mapped[int] = mapped_column("Total_puntos", Integer, nullable=False)
    point_config_id: Mapped[UUID] = mapped_column(
        "Config_punto_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.CONFIG_PUNTOS.id",
            name="fk_OPERACION_Config_punto_id_CONFIG_PUNTOS_id",
        ),
        nullable=False,
    )
