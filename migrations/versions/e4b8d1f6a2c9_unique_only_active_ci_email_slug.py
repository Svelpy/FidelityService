"""unique ci, email and slug only among active rows

Los registros se eliminan de forma lógica (is_deleted = true), por lo que las
restricciones únicas globales impedían reutilizar el ci o email de un usuario
eliminado y el slug de una categoría eliminada. Se reemplazan por índices
únicos parciales sobre filas activas, conservando los mismos nombres para que
el manejo de errores por nombre de constraint siga funcionando.

Revision ID: e4b8d1f6a2c9
Revises: d5a7c9e1f3b2
Create Date: 2026-11-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4b8d1f6a2c9"
down_revision: Union[str, Sequence[str], None] = "d5a7c9e1f3b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (tabla, columna, nombre de la constraint/índice)
_UNIQUE_FIELDS = (
    ("usuario", "ci", "uq_usuario_ci"),
    ("usuario", "email", "uq_usuario_email"),
    ("categoria", "slug", "uq_categoria_slug"),
)


def upgrade() -> None:
    # Si una transacción abierta bloquea la tabla, falla rápido en vez de
    # dejar el arranque de la API colgado esperando el lock.
    op.execute("SET LOCAL lock_timeout = '5s'")

    for table, column, name in _UNIQUE_FIELDS:
        op.execute(f"ALTER TABLE public.{table} DROP CONSTRAINT IF EXISTS {name}")
        op.execute(f"DROP INDEX IF EXISTS public.{name}")
        op.create_index(
            name,
            table,
            [column],
            unique=True,
            schema="public",
            postgresql_where=sa.text("is_deleted = false"),
        )


def downgrade() -> None:
    # Falla si ya existe un valor repetido entre un registro activo y uno
    # eliminado; en ese caso hay que resolver los duplicados manualmente.
    op.execute("SET LOCAL lock_timeout = '5s'")

    for table, column, name in reversed(_UNIQUE_FIELDS):
        op.drop_index(name, table_name=table, schema="public")
        op.create_unique_constraint(name, table, [column], schema="public")
