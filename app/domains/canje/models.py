from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.types import UserDefinedType
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class ExistingEnum(UserDefinedType):
    """Referencia al tipo PostgreSQL `enum` ya declarado en la base."""

    cache_ok = True

    def get_col_spec(self, **kwargs: object) -> str:
        return "enum"


class Canje(BaseModel):
    __tablename__ = "CANJE"
    __table_args__ = {"schema": "public"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, nullable=False)
    client_id: Mapped[UUID] = mapped_column("Cliente_id",PGUUID(as_uuid=True),ForeignKey("public.USUARIO.id",name="fk_CANJE_Cliente_id_USUARIO_id"),nullable=False)
    giver_id: Mapped[UUID | None] = mapped_column("Dador_id",PGUUID(as_uuid=True),ForeignKey("public.USUARIO.id",name="fk_CANJE_Dador_id_USUARIO_id"),nullable=True)
    voucher_id: Mapped[UUID] = mapped_column("Vale_id",PGUUID(as_uuid=True),ForeignKey("public.VALE.id",name="fk_CANJE_Vale_id_VALE_id"),nullable=False)
    status: Mapped[str] = mapped_column("Status",ExistingEnum(),nullable=False,)
