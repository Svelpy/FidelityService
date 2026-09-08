from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class FavoritoVale(BaseModel):
    __tablename__ = "FAVORITO_VALE"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(
        "User_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.USUARIO.id",
            name="fk_FAVORITO_VALE_User_id_USUARIO_id",
        ),
        nullable=False,
    )
    voucher_id: Mapped[UUID] = mapped_column(
        "Vale_id",
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.VALE.id",
            name="fk_FAVORITO_VALE_Vale_id_VALE_id",
        ),
        nullable=False,
    )
