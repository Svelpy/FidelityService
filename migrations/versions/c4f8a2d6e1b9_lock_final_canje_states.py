"""lock final canje states

Un canje CANJEADO, EXPIRADO o CANCELADO es definitivo: ninguna columna
puede modificarse una vez que abandona el estado PENDIENTE. Esto también
congela updated_at, que se utiliza como fecha efectiva del canje.

Revision ID: c4f8a2d6e1b9
Revises: b2e7f4a9c3d6
Create Date: 2026-11-09

"""
from typing import Sequence, Union

from alembic import op


revision: str = "c4f8a2d6e1b9"
down_revision: Union[str, Sequence[str], None] = "b2e7f4a9c3d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE FUNCTION public.validate_canje_estado_final()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF OLD.status <> 'PENDIENTE' THEN
                RAISE EXCEPTION
                    'Un canje en estado % no puede modificarse', OLD.status
                    USING ERRCODE = '23514',
                          CONSTRAINT = 'ck_canje_estado_final_inmutable';
            END IF;
            RETURN NEW;
        END;
        $$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_canje_estado_final_inmutable
        BEFORE UPDATE
        ON public.canje
        FOR EACH ROW
        EXECUTE FUNCTION public.validate_canje_estado_final()
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER trg_canje_estado_final_inmutable ON public.canje"
    )
    op.execute("DROP FUNCTION public.validate_canje_estado_final()")
