"""enforce role branch compatibility

ADMIN y CAJERO solo pertenecen a sucursales del negocio MAIN, y CLIENTE no
pertenece a ninguna sucursal, igual que SUPERADMIN y OWNER.

Revision ID: b2e7f4a9c3d6
Revises: a9d4e2f6b8c1
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op


revision: str = "b2e7f4a9c3d6"
down_revision: Union[str, Sequence[str], None] = "a9d4e2f6b8c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Un CAJERO de un negocio aliado cumple la función de SOCIO.
    op.execute(
        """
        UPDATE public.usuario AS u
        SET role = 'SOCIO',
            updated_at = now()
        FROM public.sucursal AS s
        JOIN public.negocio AS n ON n.id = s.negocio_id
        WHERE s.id = u.sucursal_id
          AND u.role = 'CAJERO'
          AND n.tipo = 'SOCIO'
        """
    )

    # Mover un ADMIN de negocio es una decisión de negocio: se aborta.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.usuario AS u
                JOIN public.sucursal AS s ON s.id = u.sucursal_id
                JOIN public.negocio AS n ON n.id = s.negocio_id
                WHERE u.role = 'ADMIN'
                  AND n.tipo <> 'MAIN'
            ) THEN
                RAISE EXCEPTION
                    'Existen usuarios ADMIN en sucursales de negocios que no '
                    'son MAIN; deben reasignarse antes de aplicar esta migración';
            END IF;
        END
        $$;
        """
    )

    # Una sucursal asignada a un CLIENTE no tiene significado.
    op.execute(
        """
        UPDATE public.usuario
        SET sucursal_id = NULL,
            updated_at = now()
        WHERE role = 'CLIENTE'
          AND sucursal_id IS NOT NULL
        """
    )
    op.drop_constraint(
        "ck_usuario_rol_global_sin_sucursal",
        "usuario",
        schema="public",
        type_="check",
    )
    op.create_check_constraint(
        "ck_usuario_rol_sin_sucursal",
        "usuario",
        "role NOT IN ('SUPERADMIN', 'OWNER', 'CLIENTE') OR sucursal_id IS NULL",
        schema="public",
    )

    op.execute(
        """
        CREATE FUNCTION public.validate_usuario_main_sucursal()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.role IN ('ADMIN', 'CAJERO')
               AND NEW.sucursal_id IS NOT NULL
               AND NOT EXISTS (
                   SELECT 1
                   FROM public.sucursal AS s
                   JOIN public.negocio AS n ON n.id = s.negocio_id
                   WHERE s.id = NEW.sucursal_id
                     AND n.tipo = 'MAIN'
               )
            THEN
                RAISE EXCEPTION
                    'Un usuario ADMIN o CAJERO solo puede pertenecer al negocio MAIN.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_usuario_main_sucursal_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_usuario_main_sucursal_compatible
        AFTER INSERT OR UPDATE OF role, sucursal_id
        ON public.usuario
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_usuario_main_sucursal()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_sucursal_main_roles()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF EXISTS (
                   SELECT 1
                   FROM public.usuario AS u
                   WHERE u.sucursal_id = NEW.id
                     AND u.role IN ('ADMIN', 'CAJERO')
               )
               AND NOT EXISTS (
                   SELECT 1
                   FROM public.negocio AS n
                   WHERE n.id = NEW.negocio_id
                     AND n.tipo = 'MAIN'
               )
            THEN
                RAISE EXCEPTION
                    'La sucursal de usuarios ADMIN o CAJERO debe pertenecer al negocio MAIN.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_sucursal_main_roles_negocio_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_sucursal_main_roles_negocio_compatible
        AFTER UPDATE OF negocio_id
        ON public.sucursal
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_sucursal_main_roles()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.validate_negocio_main_roles()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.tipo <> 'MAIN'
               AND EXISTS (
                   SELECT 1
                   FROM public.sucursal AS s
                   JOIN public.usuario AS u ON u.sucursal_id = s.id
                   WHERE s.negocio_id = NEW.id
                     AND u.role IN ('ADMIN', 'CAJERO')
               )
            THEN
                RAISE EXCEPTION
                    'Un negocio con usuarios ADMIN o CAJERO asignados debe conservar el tipo MAIN.'
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_negocio_main_roles_tipo_compatible';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE CONSTRAINT TRIGGER ct_negocio_main_roles_tipo_compatible
        AFTER UPDATE OF tipo
        ON public.negocio
        DEFERRABLE INITIALLY IMMEDIATE
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_negocio_main_roles()
        """
    )


def downgrade() -> None:
    # Los roles convertidos y las sucursales desvinculadas no se restauran.
    op.execute(
        "DROP TRIGGER ct_negocio_main_roles_tipo_compatible ON public.negocio"
    )
    op.execute("DROP FUNCTION public.validate_negocio_main_roles()")
    op.execute(
        "DROP TRIGGER ct_sucursal_main_roles_negocio_compatible ON public.sucursal"
    )
    op.execute("DROP FUNCTION public.validate_sucursal_main_roles()")
    op.execute(
        "DROP TRIGGER ct_usuario_main_sucursal_compatible ON public.usuario"
    )
    op.execute("DROP FUNCTION public.validate_usuario_main_sucursal()")

    op.drop_constraint(
        "ck_usuario_rol_sin_sucursal",
        "usuario",
        schema="public",
        type_="check",
    )
    op.create_check_constraint(
        "ck_usuario_rol_global_sin_sucursal",
        "usuario",
        "role NOT IN ('SUPERADMIN', 'OWNER') OR sucursal_id IS NULL",
        schema="public",
    )
