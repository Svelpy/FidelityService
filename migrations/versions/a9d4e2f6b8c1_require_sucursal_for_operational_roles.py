"""require sucursal for admin, cajero and socio

Revision ID: a9d4e2f6b8c1
Revises: f3a8c1e5d7b9
Create Date: 2026-10-31

"""
from typing import Sequence, Union

from alembic import op


revision: str = "a9d4e2f6b8c1"
down_revision: Union[str, Sequence[str], None] = "f3a8c1e5d7b9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # CAJERO y SOCIO ya requerían sucursal en el service; una fila sin ella
    # no puede corregirse automáticamente.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM public.usuario
                WHERE role IN ('CAJERO', 'SOCIO')
                  AND sucursal_id IS NULL
            ) THEN
                RAISE EXCEPTION
                    'Existen usuarios CAJERO o SOCIO sin sucursal; '
                    'deben asignarse antes de aplicar esta migración';
            END IF;
        END
        $$;
        """
    )

    # Los ADMIN sin sucursal se asignan a la única sucursal activa del
    # negocio MAIN. Si no existe exactamente una, la elección es manual.
    op.execute(
        """
        DO $$
        DECLARE
            main_sucursal_ids uuid[];
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM public.usuario
                WHERE role = 'ADMIN' AND sucursal_id IS NULL
            ) THEN
                RETURN;
            END IF;

            SELECT array_agg(s.id)
            INTO main_sucursal_ids
            FROM public.sucursal AS s
            JOIN public.negocio AS n ON n.id = s.negocio_id
            WHERE n.tipo = 'MAIN'
              AND n.is_deleted = false
              AND s.is_deleted = false;

            IF coalesce(array_length(main_sucursal_ids, 1), 0) <> 1 THEN
                RAISE EXCEPTION
                    'Existen usuarios ADMIN sin sucursal y el negocio MAIN no '
                    'tiene exactamente una sucursal activa; deben asignarse '
                    'manualmente antes de aplicar esta migración';
            END IF;

            UPDATE public.usuario
            SET sucursal_id = main_sucursal_ids[1],
                updated_at = now()
            WHERE role = 'ADMIN' AND sucursal_id IS NULL;
        END
        $$;
        """
    )

    op.create_check_constraint(
        "ck_usuario_rol_operativo_con_sucursal",
        "usuario",
        "role NOT IN ('ADMIN', 'CAJERO', 'SOCIO') OR sucursal_id IS NOT NULL",
        schema="public",
    )


def downgrade() -> None:
    # Las sucursales asignadas a ADMIN en upgrade se conservan.
    op.drop_constraint(
        "ck_usuario_rol_operativo_con_sucursal",
        "usuario",
        schema="public",
        type_="check",
    )
