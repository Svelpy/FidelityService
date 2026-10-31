"""enforce global roles without sucursal and single active owner

Revision ID: f3a8c1e5d7b9
Revises: 6d13996303bb
Create Date: 2026-10-30

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a8c1e5d7b9"
down_revision: Union[str, Sequence[str], None] = "6d13996303bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Elegir qué OWNER se conserva es una decisión de negocio: se aborta
    # en lugar de resolverlo automáticamente.
    op.execute(
        """
        DO $$
        BEGIN
            IF (
                SELECT count(*)
                FROM public.usuario
                WHERE role = 'OWNER' AND is_deleted = false
            ) > 1 THEN
                RAISE EXCEPTION
                    'Existe más de un usuario OWNER activo; '
                    'debe conservarse solo uno antes de aplicar esta migración';
            END IF;
        END
        $$;
        """
    )

    # SUPERADMIN y OWNER operan sobre todo el sistema; una sucursal asignada
    # a estos roles no tiene significado y se desvincula.
    op.execute(
        """
        UPDATE public.usuario
        SET sucursal_id = NULL,
            updated_at = now()
        WHERE role IN ('SUPERADMIN', 'OWNER')
          AND sucursal_id IS NOT NULL
        """
    )

    op.create_check_constraint(
        "ck_usuario_rol_global_sin_sucursal",
        "usuario",
        "role NOT IN ('SUPERADMIN', 'OWNER') OR sucursal_id IS NULL",
        schema="public",
    )
    op.create_index(
        "uq_usuario_owner_activo",
        "usuario",
        ["role"],
        unique=True,
        schema="public",
        postgresql_where=sa.text("role = 'OWNER' AND is_deleted = false"),
    )


def downgrade() -> None:
    # Las sucursales desvinculadas en upgrade no se restauran.
    op.drop_index(
        "uq_usuario_owner_activo",
        table_name="usuario",
        schema="public",
    )
    op.drop_constraint(
        "ck_usuario_rol_global_sin_sucursal",
        "usuario",
        schema="public",
        type_="check",
    )
