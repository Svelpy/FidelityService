from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text
from sqlmodel import Field

from app.core.base_model import BaseModel


class AuthSession(BaseModel, table=True):
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
        Index("ix_auth_sessions_replaced_by", "replaced_by"),
        {"schema": "public"},
    )

    user_id: UUID = Field(
        foreign_key="public.usuario.id",
        nullable=False,
    )
    family_id: UUID = Field(
        default_factory=uuid4,
        nullable=False,
    )
    refresh_token_hash: str = Field(
        sa_type=String(64),
        nullable=False,
    )
    expires_at: datetime = Field(
        sa_type=DateTime(timezone=True),
        nullable=False,
    )
    last_used_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    revoked_at: datetime | None = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
    )
    revocation_reason: str | None = Field(
        default=None,
        sa_type=String(64),
        nullable=True,
    )
    replaced_by: UUID | None = Field(
        default=None,
        foreign_key="public.auth_sessions.id",
        nullable=True,
    )
    user_agent: str | None = Field(default=None, sa_type=Text, nullable=True)
    ip_address: str | None = Field(
        default=None,
        max_length=45,
        nullable=True,
    )
