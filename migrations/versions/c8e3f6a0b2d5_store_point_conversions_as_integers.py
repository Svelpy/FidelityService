"""store point conversions as integers

Revision ID: c8e3f6a0b2d5
Revises: b7d2e5f9a1c4
Create Date: 2026-10-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8e3f6a0b2d5"
down_revision: Union[str, Sequence[str], None] = "b7d2e5f9a1c4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "config_puntos",
        sa.Column("asignacion_bolivianos", sa.BigInteger(), nullable=True),
        schema="public",
    )
    op.add_column(
        "config_puntos",
        sa.Column("asignacion_puntos", sa.BigInteger(), nullable=True),
        schema="public",
    )
    op.add_column(
        "config_puntos",
        sa.Column("costo_vale_bolivianos", sa.BigInteger(), nullable=True),
        schema="public",
    )
    op.add_column(
        "config_puntos",
        sa.Column("costo_vale_puntos", sa.BigInteger(), nullable=True),
        schema="public",
    )
    op.add_column(
        "config_puntos",
        sa.Column("status", sa.String(length=8), nullable=True),
        schema="public",
    )

    op.execute(
        """
        UPDATE public.config_puntos
        SET asignacion_bolivianos = 1000000,
            asignacion_puntos = (factor_asignacion_puntos * 1000000)::bigint,
            costo_vale_bolivianos = 1000000,
            costo_vale_puntos = (factor_costo_vale * 1000000)::bigint,
            status = CASE
                WHEN end_date IS NULL THEN 'ACTIVE'
                ELSE 'INACTIVE'
            END
        """
    )

    for column_name in (
        "asignacion_bolivianos",
        "asignacion_puntos",
        "costo_vale_bolivianos",
        "costo_vale_puntos",
        "status",
    ):
        op.alter_column(
            "config_puntos",
            column_name,
            nullable=False,
            schema="public",
        )

    op.drop_index(
        "uq_config_puntos_activa",
        table_name="config_puntos",
        schema="public",
    )
    op.drop_constraint(
        "ck_config_puntos_factor_asignacion_positivo",
        "config_puntos",
        schema="public",
        type_="check",
    )
    op.drop_constraint(
        "ck_config_puntos_factor_costo_positivo",
        "config_puntos",
        schema="public",
        type_="check",
    )
    op.drop_constraint(
        "ck_config_puntos_rango_fechas",
        "config_puntos",
        schema="public",
        type_="check",
    )
    op.drop_column("config_puntos", "factor_asignacion_puntos", schema="public")
    op.drop_column("config_puntos", "factor_costo_vale", schema="public")

    op.create_check_constraint(
        "estado_config_puntos",
        "config_puntos",
        "status IN ('ACTIVE', 'INACTIVE')",
        schema="public",
    )
    op.create_check_constraint(
        "ck_config_puntos_asignacion_positiva",
        "config_puntos",
        "asignacion_bolivianos > 0 AND asignacion_puntos > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_config_puntos_costo_vale_positivo",
        "config_puntos",
        "costo_vale_bolivianos > 0 AND costo_vale_puntos > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_config_puntos_rango_fechas",
        "config_puntos",
        "(status = 'ACTIVE' AND end_date IS NULL) OR "
        "(status = 'INACTIVE' AND end_date > start_date)",
        schema="public",
    )
    op.create_index(
        "uq_config_puntos_activa",
        "config_puntos",
        [sa.literal_column("(true)")],
        unique=True,
        schema="public",
        postgresql_where=sa.text("status = 'ACTIVE' AND is_deleted = false"),
    )


def downgrade() -> None:
    op.add_column(
        "config_puntos",
        sa.Column("factor_asignacion_puntos", sa.Numeric(18, 6), nullable=True),
        schema="public",
    )
    op.add_column(
        "config_puntos",
        sa.Column("factor_costo_vale", sa.Numeric(18, 6), nullable=True),
        schema="public",
    )
    op.execute(
        """
        UPDATE public.config_puntos
        SET factor_asignacion_puntos = round(
                asignacion_puntos::numeric / asignacion_bolivianos,
                6
            ),
            factor_costo_vale = round(
                costo_vale_puntos::numeric / costo_vale_bolivianos,
                6
            )
        """
    )
    op.alter_column(
        "config_puntos",
        "factor_asignacion_puntos",
        nullable=False,
        schema="public",
    )
    op.alter_column(
        "config_puntos",
        "factor_costo_vale",
        nullable=False,
        schema="public",
    )

    op.drop_index(
        "uq_config_puntos_activa",
        table_name="config_puntos",
        schema="public",
    )
    for constraint_name in (
        "estado_config_puntos",
        "ck_config_puntos_asignacion_positiva",
        "ck_config_puntos_costo_vale_positivo",
        "ck_config_puntos_rango_fechas",
    ):
        op.drop_constraint(
            constraint_name,
            "config_puntos",
            schema="public",
            type_="check",
        )

    for column_name in (
        "status",
        "costo_vale_puntos",
        "costo_vale_bolivianos",
        "asignacion_puntos",
        "asignacion_bolivianos",
    ):
        op.drop_column("config_puntos", column_name, schema="public")

    op.create_check_constraint(
        "ck_config_puntos_factor_asignacion_positivo",
        "config_puntos",
        "factor_asignacion_puntos > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_config_puntos_factor_costo_positivo",
        "config_puntos",
        "factor_costo_vale > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_config_puntos_rango_fechas",
        "config_puntos",
        "end_date IS NULL OR end_date > start_date",
        schema="public",
    )
    op.create_index(
        "uq_config_puntos_activa",
        "config_puntos",
        [sa.literal_column("(true)")],
        unique=True,
        schema="public",
        postgresql_where=sa.text("end_date IS NULL AND is_deleted = false"),
    )
