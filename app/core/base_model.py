from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped, mapped_column


class BaseModel(DeclarativeBase):
    """Base declarativa con los campos comunes de auditoría."""

    __abstract__ = True

    create_at: Mapped[datetime] = mapped_column(DateTime(timezone=False),nullable=False)
    create_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True),nullable=True)
    update_at: Mapped[datetime] = mapped_column(DateTime(timezone=False),nullable=False)
    update_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True),nullable=True)
    is_delete: Mapped[bool] = mapped_column(Boolean, nullable=False)
    delete_by: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True),nullable=True)
    delete_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=False),nullable=True)


Base = BaseModel
