"""update operation fields and constraints

Revision ID: 47c12af38d91
Revises: cbdd58d47df7
Create Date: 2026-10-12

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "47c12af38d91"
down_revision: Union[str, Sequence[str], None] = "cbdd58d47df7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "operacion",
        "referencia",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
        schema="public",
    )
    op.create_check_constraint(
        "ck_operacion_total_compra_positivo",
        "operacion",
        "total_compra > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_operacion_total_puntos_positivo",
        "operacion",
        "total_puntos > 0",
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_operacion_total_puntos_positivo",
        "operacion",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_operacion_total_compra_positivo",
        "operacion",
        type_="check",
        schema="public",
    )
    op.alter_column(
        "operacion",
        "referencia",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
        schema="public",
    )
