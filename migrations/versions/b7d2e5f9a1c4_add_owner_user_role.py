"""add owner user role

Revision ID: b7d2e5f9a1c4
Revises: a6c1d4e8f2b7
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b7d2e5f9a1c4"
down_revision: Union[str, Sequence[str], None] = "a6c1d4e8f2b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        "role_usuario",
        "usuario",
        schema="public",
        type_="check",
    )
    op.create_check_constraint(
        "role_usuario",
        "usuario",
        "role IN ('SUPERADMIN', 'OWNER', 'ADMIN', 'CAJERO', 'CLIENTE', 'SOCIO')",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "role_usuario",
        "usuario",
        schema="public",
        type_="check",
    )
    op.create_check_constraint(
        "role_usuario",
        "usuario",
        "role IN ('SUPERADMIN', 'ADMIN', 'CAJERO', 'CLIENTE', 'SOCIO')",
        schema="public",
    )
