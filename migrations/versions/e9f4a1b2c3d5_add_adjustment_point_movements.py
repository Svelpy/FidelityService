"""add adjustment point movements

Revision ID: e9f4a1b2c3d5
Revises: c8d3f2e6a0b4
Create Date: 2026-10-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e9f4a1b2c3d5"
down_revision: Union[str, Sequence[str], None] = "c8d3f2e6a0b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE public.tipo_movimiento ADD VALUE 'AJUSTE'")

    op.add_column(
        "movimientos_puntos",
        sa.Column("movimiento_origen_id", sa.Uuid(), nullable=True),
        schema="public",
    )
    op.create_foreign_key(
        "fk_movimientos_puntos_movimiento_origen_id",
        "movimientos_puntos",
        "movimientos_puntos",
        ["movimiento_origen_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
    )
    op.create_unique_constraint(
        "uq_movimientos_puntos_movimiento_origen_id",
        "movimientos_puntos",
        ["movimiento_origen_id"],
        schema="public",
    )
    op.create_index(
        "ix_movimientos_puntos_movimiento_origen_id",
        "movimientos_puntos",
        ["movimiento_origen_id"],
        unique=False,
        schema="public",
    )
    op.drop_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )
    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        "(tipo_movimiento = 'ACUMULA' "
        "AND operacion_id IS NOT NULL AND canje_id IS NULL "
        "AND movimiento_origen_id IS NULL) OR "
        "(tipo_movimiento = 'CANJE' "
        "AND canje_id IS NOT NULL AND operacion_id IS NULL "
        "AND movimiento_origen_id IS NULL) OR "
        "(tipo_movimiento = 'AJUSTE' "
        "AND operacion_id IS NULL AND canje_id IS NULL)",
        schema="public",
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.movimientos_puntos
                WHERE tipo_movimiento::text = 'AJUSTE'
            ) THEN
                RAISE EXCEPTION
                    'Existen movimientos AJUSTE; deben resolverse antes del downgrade';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )
    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        "(tipo_movimiento = 'ACUMULA' "
        "AND operacion_id IS NOT NULL AND canje_id IS NULL) OR "
        "(tipo_movimiento = 'CANJE' "
        "AND canje_id IS NOT NULL AND operacion_id IS NULL)",
        schema="public",
    )
    op.drop_index(
        "ix_movimientos_puntos_movimiento_origen_id",
        table_name="movimientos_puntos",
        schema="public",
    )
    op.drop_constraint(
        "uq_movimientos_puntos_movimiento_origen_id",
        "movimientos_puntos",
        type_="unique",
        schema="public",
    )
    op.drop_constraint(
        "fk_movimientos_puntos_movimiento_origen_id",
        "movimientos_puntos",
        type_="foreignkey",
        schema="public",
    )
    op.drop_column(
        "movimientos_puntos",
        "movimiento_origen_id",
        schema="public",
    )

    op.execute(
        "ALTER TYPE public.tipo_movimiento RENAME TO tipo_movimiento_old"
    )
    op.execute(
        "CREATE TYPE public.tipo_movimiento AS ENUM ('ACUMULA', 'CANJE')"
    )
    op.execute(
        "ALTER TABLE public.movimientos_puntos "
        "ALTER COLUMN tipo_movimiento TYPE public.tipo_movimiento "
        "USING tipo_movimiento::text::public.tipo_movimiento"
    )
    op.execute("DROP TYPE public.tipo_movimiento_old")
