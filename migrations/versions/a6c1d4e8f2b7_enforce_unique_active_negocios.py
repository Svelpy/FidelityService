"""enforce unique active negocios

Revision ID: a6c1d4e8f2b7
Revises: e9f4a1b2c3d5
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a6c1d4e8f2b7"
down_revision: Union[str, Sequence[str], None] = "e9f4a1b2c3d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "uq_negocio_nombre_activo_ci",
        "negocio",
        [sa.text("lower(nombre)")],
        unique=True,
        schema="public",
        postgresql_where=sa.text("is_deleted = false"),
    )
    op.create_index(
        "uq_negocio_main_activo",
        "negocio",
        ["tipo"],
        unique=True,
        schema="public",
        postgresql_where=sa.text(
            "tipo = 'MAIN' AND is_deleted = false"
        ),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_negocio_main_activo",
        table_name="negocio",
        schema="public",
    )
    op.drop_index(
        "uq_negocio_nombre_activo_ci",
        table_name="negocio",
        schema="public",
    )
