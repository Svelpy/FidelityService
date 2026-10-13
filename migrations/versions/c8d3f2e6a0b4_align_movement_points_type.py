"""align movement points type

Revision ID: c8d3f2e6a0b4
Revises: b7c2e1d5f9a3
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8d3f2e6a0b4"
down_revision: Union[str, Sequence[str], None] = "b7c2e1d5f9a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.movimientos_puntos
                WHERE puntos > 2147483647
            ) THEN
                RAISE EXCEPTION
                    'Existen movimientos con puntos fuera del rango INTEGER; '
                    'deben resolverse antes de migrar';
            END IF;
        END
        $$;
        """
    )
    op.alter_column(
        "movimientos_puntos",
        "puntos",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        schema="public",
    )


def downgrade() -> None:
    op.alter_column(
        "movimientos_puntos",
        "puntos",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        schema="public",
    )
