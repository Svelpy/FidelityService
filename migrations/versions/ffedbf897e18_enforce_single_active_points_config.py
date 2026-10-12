"""enforce single active points config

Revision ID: ffedbf897e18
Revises: bdfa7dde0349
Create Date: 2026-10-12 10:47:24.835594

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ffedbf897e18'
down_revision: Union[str, Sequence[str], None] = 'bdfa7dde0349'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        "uq_config_puntos_activa",
        "config_puntos",
        [sa.literal_column("(true)")],
        unique=True,
        schema="public",
        postgresql_where=sa.text("end_date IS NULL AND is_deleted = false"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        "uq_config_puntos_activa",
        table_name="config_puntos",
        schema="public",
    )
