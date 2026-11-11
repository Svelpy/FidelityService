"""add operation cancellation

Revision ID: d5a7c9e1f3b2
Revises: c4f8a2d6e1b9
Create Date: 2026-11-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d5a7c9e1f3b2"
down_revision: Union[str, Sequence[str], None] = "c4f8a2d6e1b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_MOVEMENT_CHECK_WITHOUT_REVERSAL = (
    "(tipo_movimiento = 'ACUMULA' "
    "AND operacion_id IS NOT NULL AND canje_id IS NULL "
    "AND movimiento_origen_id IS NULL) OR "
    "(tipo_movimiento = 'CANJE' "
    "AND canje_id IS NOT NULL AND operacion_id IS NULL "
    "AND movimiento_origen_id IS NULL) OR "
    "(tipo_movimiento = 'AJUSTE' "
    "AND operacion_id IS NULL AND canje_id IS NULL)"
)


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE public.tipo_movimiento ADD VALUE IF NOT EXISTS 'REVERSA'")

    op.drop_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )
    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        _MOVEMENT_CHECK_WITHOUT_REVERSAL
        + " OR (tipo_movimiento = 'REVERSA' "
        "AND movimiento_origen_id IS NOT NULL "
        "AND operacion_id IS NULL AND canje_id IS NULL)",
        schema="public",
    )

    op.add_column(
        "operacion",
        sa.Column("anulada_at", sa.DateTime(timezone=True), nullable=True),
        schema="public",
    )
    op.add_column(
        "operacion",
        sa.Column("anulada_por", sa.Uuid(), nullable=True),
        schema="public",
    )
    op.add_column(
        "operacion",
        sa.Column("motivo_anulacion", sa.String(length=255), nullable=True),
        schema="public",
    )
    op.create_foreign_key(
        "fk_operacion_anulada_por",
        "operacion",
        "usuario",
        ["anulada_por"],
        ["id"],
        source_schema="public",
        referent_schema="public",
    )
    op.create_check_constraint(
        "ck_operacion_anulacion_consistente",
        "operacion",
        "(anulada_at IS NULL AND anulada_por IS NULL "
        "AND motivo_anulacion IS NULL) OR "
        "(anulada_at IS NOT NULL AND anulada_por IS NOT NULL "
        "AND motivo_anulacion IS NOT NULL)",
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
                WHERE tipo_movimiento::text = 'REVERSA'
            ) OR EXISTS (
                SELECT 1
                FROM public.operacion
                WHERE anulada_at IS NOT NULL
            ) THEN
                RAISE EXCEPTION
                    'Existen operaciones anuladas; deben resolverse antes del downgrade';
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint(
        "ck_operacion_anulacion_consistente",
        "operacion",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "fk_operacion_anulada_por",
        "operacion",
        type_="foreignkey",
        schema="public",
    )
    op.drop_column("operacion", "motivo_anulacion", schema="public")
    op.drop_column("operacion", "anulada_por", schema="public")
    op.drop_column("operacion", "anulada_at", schema="public")

    op.drop_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        type_="check",
        schema="public",
    )
    op.create_check_constraint(
        "ck_movimientos_puntos_referencia_por_tipo",
        "movimientos_puntos",
        _MOVEMENT_CHECK_WITHOUT_REVERSAL,
        schema="public",
    )

    op.execute(
        "ALTER TYPE public.tipo_movimiento RENAME TO tipo_movimiento_old"
    )
    op.execute(
        "CREATE TYPE public.tipo_movimiento AS ENUM ('ACUMULA', 'CANJE', 'AJUSTE')"
    )
    op.execute(
        "ALTER TABLE public.movimientos_puntos "
        "ALTER COLUMN tipo_movimiento TYPE public.tipo_movimiento "
        "USING tipo_movimiento::text::public.tipo_movimiento"
    )
    op.execute("DROP TYPE public.tipo_movimiento_old")
