"""add password reset tokens

Revision ID: 6d13996303bb
Revises: c8e3f6a0b2d5
Create Date: 2026-10-29 08:46:26.064959

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d13996303bb'
down_revision: Union[str, Sequence[str], None] = 'c8e3f6a0b2d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PENDING_TOKEN_CONDITION = 'used_at IS NULL AND revoked_at IS NULL AND is_deleted = false'


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('password_reset_tokens',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('is_deleted', sa.Boolean(), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('deleted_by', sa.Uuid(), nullable=True),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint('expires_at > created_at', name='ck_password_reset_tokens_expiration_after_creation'),
    sa.CheckConstraint('used_at IS NULL OR revoked_at IS NULL', name='ck_password_reset_tokens_used_or_revoked'),
    sa.ForeignKeyConstraint(['user_id'], ['public.usuario.id'], ),
    sa.PrimaryKeyConstraint('id'),
    schema='public'
    )
    op.create_index('ix_password_reset_tokens_expires_at', 'password_reset_tokens', ['expires_at'], unique=False, schema='public')
    op.create_index(op.f('ix_public_password_reset_tokens_is_deleted'), 'password_reset_tokens', ['is_deleted'], unique=False, schema='public')
    op.create_index('ux_password_reset_tokens_token_hash', 'password_reset_tokens', ['token_hash'], unique=True, schema='public')
    op.create_index('ux_password_reset_tokens_user_id_pending', 'password_reset_tokens', ['user_id'], unique=True, schema='public', postgresql_where=sa.text(PENDING_TOKEN_CONDITION))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_password_reset_tokens_user_id_pending', table_name='password_reset_tokens', schema='public', postgresql_where=sa.text(PENDING_TOKEN_CONDITION))
    op.drop_index('ux_password_reset_tokens_token_hash', table_name='password_reset_tokens', schema='public')
    op.drop_index(op.f('ix_public_password_reset_tokens_is_deleted'), table_name='password_reset_tokens', schema='public')
    op.drop_index('ix_password_reset_tokens_expires_at', table_name='password_reset_tokens', schema='public')
    op.drop_table('password_reset_tokens', schema='public')
