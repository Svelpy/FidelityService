from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, update
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class AuthSession(BaseModel):
    __tablename__ = "auth_sessions"
    __table_args__ = (
        Index(
            "ux_auth_sessions_refresh_token_hash",
            "refresh_token_hash",
            unique=True,
        ),
        Index(
            "ix_auth_sessions_user_id_revoked_at",
            "user_id",
            "revoked_at",
        ),
        Index(
            "ix_auth_sessions_family_id_revoked_at",
            "family_id",
            "revoked_at",
        ),
        Index("ix_auth_sessions_expires_at", "expires_at"),
        {"schema": "public"},
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.USUARIO.id",
            name="fk_auth_sessions_user_id_USUARIO_id",
        ),
        nullable=False,
    )
    family_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        default=uuid4,
        nullable=False,
    )
    refresh_token_hash: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revocation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    replaced_by: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "public.auth_sessions.id",
            name="fk_auth_sessions_replaced_by_auth_sessions_id",
        ),
        nullable=True,
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)

    @classmethod
    async def revoke_for_user(
        cls,
        session: AsyncSession,
        user_id: UUID,
        reason: str,
    ) -> None:
        await session.execute(
            update(cls)
            .where(cls.user_id == user_id, cls.revoked_at.is_(None))
            .values(
                revoked_at=datetime.now(timezone.utc),
                revocation_reason=reason,
            )
        )
