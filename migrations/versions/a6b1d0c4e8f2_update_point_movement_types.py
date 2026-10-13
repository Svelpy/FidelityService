"""update point movement types and constraints

Revision ID: a6b1d0c4e8f2
Revises: 47c12af38d91
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a6b1d0c4e8f2"
down_revision: Union[str, Sequence[str], None] = "47c12af38d91"
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
                WHERE tipo_movimiento::text NOT IN ('ACUMULA', 'CANJE')
            ) THEN
                RAISE EXCEPTION
                    'Existen movimientos AJUSTE o EXPIRA; '
                    'deben resolverse antes de actualizar tipo_movimiento';
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

    op.execute(
        "ALTER TYPE public.tipo_movimiento "
        "RENAME TO tipo_movimiento_old"
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

    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        "(tipo_movimiento = 'ACUMULA' "
        "AND operacion_id IS NOT NULL AND canje_id IS NULL) OR "
        "(tipo_movimiento = 'CANJE' "
        "AND canje_id IS NOT NULL AND operacion_id IS NULL)",
        schema="public",
    )
    op.create_check_constraint(
        "ck_movimientos_puntos_cantidad_por_tipo",
        "movimientos_puntos",
        "puntos > 0",
        schema="public",
    )
    op.create_unique_constraint(
        "uq_movimientos_puntos_operacion_id",
        "movimientos_puntos",
        ["operacion_id"],
        schema="public",
    )
    op.create_unique_constraint(
        "uq_movimientos_puntos_canje_id",
        "movimientos_puntos",
        ["canje_id"],
        schema="public",
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_movimientos_puntos_canje_id",
        "movimientos_puntos",
        type_="unique",
        schema="public",
    )
    op.drop_constraint(
        "uq_movimientos_puntos_operacion_id",
        "movimientos_puntos",
        type_="unique",
        schema="public",
    )
    op.drop_constraint(
        "ck_movimientos_puntos_cantidad_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )

    op.execute(
        "ALTER TYPE public.tipo_movimiento "
        "RENAME TO tipo_movimiento_old"
    )
    op.execute(
        "CREATE TYPE public.tipo_movimiento AS ENUM "
        "('ACUMULA', 'CANJE', 'AJUSTE', 'EXPIRA')"
    )
    op.execute(
        "ALTER TABLE public.movimientos_puntos "
        "ALTER COLUMN tipo_movimiento TYPE public.tipo_movimiento "
        "USING tipo_movimiento::text::public.tipo_movimiento"
    )
    op.execute("DROP TYPE public.tipo_movimiento_old")

    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        "(tipo_movimiento = 'ACUMULA' "
        "AND operacion_id IS NOT NULL AND canje_id IS NULL) OR "
        "(tipo_movimiento = 'CANJE' "
        "AND canje_id IS NOT NULL AND operacion_id IS NULL) OR "
        "(tipo_movimiento IN ('AJUSTE', 'EXPIRA') "
        "AND operacion_id IS NULL AND canje_id IS NULL)",
        schema="public",
    )
