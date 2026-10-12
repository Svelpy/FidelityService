"""enforce socio branch compatibility

Revision ID: bdfa7dde0349
Revises: 8e313ef78f66
Create Date: 2026-10-12 08:49:18.393721

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'bdfa7dde0349'
down_revision: Union[str, Sequence[str], None] = '8e313ef78f66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        """
        CREATE FUNCTION public.validate_usuario_socio_sucursal()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.role = 'SOCIO'
               AND NEW.sucursal_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1
                   FROM public.sucursal AS s
                   JOIN public.negocio AS n ON n.id = s.negocio_id
                   WHERE s.id = NEW.sucursal_id
                     AND n.tipo = 'SOCIO'
               )
            THEN
                RAISE EXCEPTION
                    'Un usuario SOCIO solo puede pertenecer a un negocio SOCIO.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_usuario_socio_sucursal_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_usuario_socio_sucursal_compatible
        AFTER INSERT OR UPDATE OF role, sucursal_id
        ON public.usuario
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_usuario_socio_sucursal()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_sucursal_socios()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                   SELECT 1
                   FROM public.usuario AS u
                   WHERE u.sucursal_id = NEW.id
                     AND u.role = 'SOCIO'
               )
               AND NOT EXISTS (
                   SELECT 1
                   FROM public.negocio AS n
                   WHERE n.id = NEW.negocio_id
                     AND n.tipo = 'SOCIO'
               )
            THEN
                RAISE EXCEPTION
                    'La sucursal de usuarios SOCIO debe pertenecer a un negocio SOCIO.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_sucursal_socios_negocio_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_sucursal_socios_negocio_compatible
        AFTER UPDATE OF negocio_id
        ON public.sucursal
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_sucursal_socios()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_negocio_socios()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.tipo <> 'SOCIO'
               AND EXISTS (
                   SELECT 1
                   FROM public.sucursal AS s
                   JOIN public.usuario AS u ON u.sucursal_id = s.id
                   WHERE s.negocio_id = NEW.id
                     AND u.role = 'SOCIO'
               )
            THEN
                RAISE EXCEPTION
                    'Un negocio con usuarios SOCIO asignados debe conservar el tipo SOCIO.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_negocio_socios_tipo_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_negocio_socios_tipo_compatible
        AFTER UPDATE OF tipo
        ON public.negocio
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_negocio_socios()
        """
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "DROP TRIGGER ct_negocio_socios_tipo_compatible ON public.negocio"
    )
    op.execute("DROP FUNCTION public.validate_negocio_socios()")
    op.execute(
        "DROP TRIGGER ct_sucursal_socios_negocio_compatible ON public.sucursal"
    )
    op.execute("DROP FUNCTION public.validate_sucursal_socios()")
    op.execute(
        "DROP TRIGGER ct_usuario_socio_sucursal_compatible ON public.usuario"
    )
    op.execute("DROP FUNCTION public.validate_usuario_socio_sucursal()")
