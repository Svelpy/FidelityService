"""update vale fields and constraints

Revision ID: cbdd58d47df7
Revises: ffedbf897e18
Create Date: 2026-10-12 11:37:02.119175

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'cbdd58d47df7'
down_revision: Union[str, Sequence[str], None] = 'ffedbf897e18'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "vale",
        "imagen_url",
        new_column_name="image_url",
        existing_type=sa.String(length=2048),
        existing_nullable=True,
        schema="public",
    )
    op.alter_column(
        "vale",
        "nombre",
        existing_type=sa.String(length=160),
        type_=sa.String(length=60),
        existing_nullable=False,
        schema="public",
    )
    op.alter_column(
        "vale",
        "descripcion",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
        schema="public",
    )
    op.create_check_constraint(
        "ck_vale_total_costo_positivo",
        "vale",
        "total_costo > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_vale_total_puntos_positivo",
        "vale",
        "total_puntos > 0",
        schema="public",
    )
    op.create_index(
        "ix_vale_nombre",
        "vale",
        ["nombre"],
        unique=False,
        schema="public",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_vale_nombre", table_name="vale", schema="public")
    op.drop_constraint(
        "ck_vale_total_puntos_positivo",
        "vale",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_vale_total_costo_positivo",
        "vale",
        type_="check",
        schema="public",
    )
    op.alter_column(
        "vale",
        "descripcion",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
        schema="public",
    )
    op.alter_column(
        "vale",
        "nombre",
        existing_type=sa.String(length=60),
        type_=sa.String(length=160),
        existing_nullable=False,
        schema="public",
    )
    op.alter_column(
        "vale",
        "image_url",
        new_column_name="imagen_url",
        existing_type=sa.String(length=2048),
        existing_nullable=True,
        schema="public",
    )
