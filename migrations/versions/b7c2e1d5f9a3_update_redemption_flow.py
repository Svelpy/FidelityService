"""update redemption flow

Revision ID: b7c2e1d5f9a3
Revises: a6b1d0c4e8f2
Create Date: 2026-10-13

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c2e1d5f9a3"
down_revision: Union[str, Sequence[str], None] = "a6b1d0c4e8f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.canje
                WHERE status = 'CANJEADO'
                  AND dador_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existen canjes CANJEADO sin dador_id; '
                    'deben resolverse antes de migrar';
            END IF;
        END
        $$;
        """
    )

    op.drop_constraint(
        "fk_canje_sucursal_negocio",
        "canje",
        type_="foreignkey",
        schema="public",
    )
    op.drop_constraint(
        "fk_canje_vale_negocio",
        "canje",
        type_="foreignkey",
        schema="public",
    )
    op.create_foreign_key(
        "fk_canje_sucursal_id",
        "canje",
        "sucursal",
        ["sucursal_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
    )
    op.create_foreign_key(
        "fk_canje_vale_id",
        "canje",
        "vale",
        ["vale_id"],
        ["id"],
        source_schema="public",
        referent_schema="public",
    )

    op.alter_column(
        "canje",
        "sucursal_id",
        existing_type=sa.Uuid(),
        nullable=True,
        schema="public",
    )
    op.execute(
        "UPDATE public.canje "
        "SET dador_id = NULL, sucursal_id = NULL "
        "WHERE status IN ('PENDIENTE', 'EXPIRADO', 'CANCELADO')"
    )

    op.drop_constraint(
        "ck_canje_codigo_seis_digitos",
        "canje",
        type_="check",
        schema="public",
    )
    op.alter_column(
        "canje",
        "codigo_canje",
        existing_type=sa.String(length=6),
        type_=sa.String(length=8),
        existing_nullable=False,
        schema="public",
    )
    op.execute(
        "UPDATE public.canje SET codigo_canje = '00' || codigo_canje"
    )
    op.create_check_constraint(
        "ck_canje_codigo_ocho_digitos",
        "canje",
        "codigo_canje ~ '^[0-9]{8}$'",
        schema="public",
    )

    op.alter_column(
        "canje",
        "referencia",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_total_puntos_positivo",
        "canje",
        "total_puntos > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_total_costo_positivo",
        "canje",
        "total_costo > 0",
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_expiracion_posterior_creacion",
        "canje",
        "expires_at > created_at",
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_cliente_dador_diferentes",
        "canje",
        "dador_id IS NULL OR dador_id <> cliente_id",
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_dador_sucursal_segun_estado",
        "canje",
        "(status = 'CANJEADO' AND dador_id IS NOT NULL "
        "AND sucursal_id IS NOT NULL) OR "
        "(status IN ('PENDIENTE', 'EXPIRADO', 'CANCELADO') "
        "AND dador_id IS NULL AND sucursal_id IS NULL)",
        schema="public",
    )

    op.drop_index(
        "ix_canje_negocio_id",
        table_name="canje",
        schema="public",
    )
    op.drop_column("canje", "negocio_id", schema="public")

    op.execute(
        """
        CREATE FUNCTION public.validate_canje_business_compatibility()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.sucursal_id IS NOT NULL AND NOT EXISTS (
                SELECT 1
                FROM public.vale AS v
                JOIN public.sucursal AS s
                  ON s.negocio_id = v.negocio_id
                WHERE v.id = NEW.vale_id
                  AND s.id = NEW.sucursal_id
            ) THEN
                RAISE EXCEPTION
                    'El vale y la sucursal deben pertenecer al mismo negocio'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_canje_negocio_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ck_canje_negocio_compatible
        AFTER INSERT OR UPDATE OF vale_id, sucursal_id
        ON public.canje
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_canje_business_compatibility()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_vale_canje_business_compatibility()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.canje AS c
                JOIN public.sucursal AS s ON s.id = c.sucursal_id
                WHERE c.vale_id = NEW.id
                  AND s.negocio_id <> NEW.negocio_id
            ) THEN
                RAISE EXCEPTION
                    'El cambio dejaría canjes asociados a otro negocio'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_canje_negocio_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ck_vale_canje_negocio_compatible
        AFTER UPDATE OF negocio_id
        ON public.vale
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_vale_canje_business_compatibility()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_sucursal_canje_business_compatibility()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.canje AS c
                JOIN public.vale AS v ON v.id = c.vale_id
                WHERE c.sucursal_id = NEW.id
                  AND v.negocio_id <> NEW.negocio_id
            ) THEN
                RAISE EXCEPTION
                    'El cambio dejaría canjes asociados a otro negocio'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_canje_negocio_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ck_sucursal_canje_negocio_compatible
        AFTER UPDATE OF negocio_id
        ON public.sucursal
        DEFERRABLE INITIALLY DEFERRED
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_sucursal_canje_business_compatibility()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER ck_sucursal_canje_negocio_compatible "
        "ON public.sucursal"
    )
    op.execute(
        "DROP FUNCTION "
        "public.validate_sucursal_canje_business_compatibility()"
    )
    op.execute(
        "DROP TRIGGER ck_vale_canje_negocio_compatible ON public.vale"
    )
    op.execute(
        "DROP FUNCTION public.validate_vale_canje_business_compatibility()"
    )
    op.execute(
        "DROP TRIGGER ck_canje_negocio_compatible ON public.canje"
    )
    op.execute(
        "DROP FUNCTION public.validate_canje_business_compatibility()"
    )

    op.add_column(
        "canje",
        sa.Column("negocio_id", sa.Uuid(), nullable=True),
        schema="public",
    )
    op.execute(
        "UPDATE public.canje AS c "
        "SET negocio_id = v.negocio_id "
        "FROM public.vale AS v "
        "WHERE v.id = c.vale_id"
    )
    op.alter_column(
        "canje",
        "negocio_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema="public",
    )
    op.create_index(
        "ix_canje_negocio_id",
        "canje",
        ["negocio_id"],
        unique=False,
        schema="public",
    )

    op.drop_constraint(
        "ck_canje_dador_sucursal_segun_estado",
        "canje",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_canje_cliente_dador_diferentes",
        "canje",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_canje_expiracion_posterior_creacion",
        "canje",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_canje_total_costo_positivo",
        "canje",
        type_="check",
        schema="public",
    )
    op.drop_constraint(
        "ck_canje_total_puntos_positivo",
        "canje",
        type_="check",
        schema="public",
    )

    op.alter_column(
        "canje",
        "referencia",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
        schema="public",
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.canje
                WHERE codigo_canje !~ '^00[0-9]{6}$'
            ) THEN
                RAISE EXCEPTION
                    'Existen códigos nuevos que no pueden volver a seis dígitos';
            END IF;
            IF EXISTS (
                SELECT 1
                FROM public.canje
                WHERE sucursal_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existen canjes sin sucursal; no puede restaurarse NOT NULL';
            END IF;
        END
        $$;
        """
    )
    op.drop_constraint(
        "ck_canje_codigo_ocho_digitos",
        "canje",
        type_="check",
        schema="public",
    )
    op.execute(
        "UPDATE public.canje SET codigo_canje = substring(codigo_canje FROM 3)"
    )
    op.alter_column(
        "canje",
        "codigo_canje",
        existing_type=sa.String(length=8),
        type_=sa.String(length=6),
        existing_nullable=False,
        schema="public",
    )
    op.create_check_constraint(
        "ck_canje_codigo_seis_digitos",
        "canje",
        "codigo_canje ~ '^[0-9]{6}$'",
        schema="public",
    )

    op.alter_column(
        "canje",
        "sucursal_id",
        existing_type=sa.Uuid(),
        nullable=False,
        schema="public",
    )
    op.drop_constraint(
        "fk_canje_vale_id",
        "canje",
        type_="foreignkey",
        schema="public",
    )
    op.drop_constraint(
        "fk_canje_sucursal_id",
        "canje",
        type_="foreignkey",
        schema="public",
    )
    op.create_foreign_key(
        "fk_canje_vale_negocio",
        "canje",
        "vale",
        ["vale_id", "negocio_id"],
        ["id", "negocio_id"],
        source_schema="public",
        referent_schema="public",
    )
    op.create_foreign_key(
        "fk_canje_sucursal_negocio",
        "canje",
        "sucursal",
        ["sucursal_id", "negocio_id"],
        ["id", "negocio_id"],
        source_schema="public",
        referent_schema="public",
    )
