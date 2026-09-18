"""add smart layout rule timestamp defaults

Revision ID: 0a36da107eee
Revises: ...
Create Date: ...
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0a36da107eee'

# NON copiare un valore inventato qui:
# lascia il down_revision generato da Alembic nel tuo file.
down_revision: Union[str, None] = 'a640d1ef7065'

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'table_combination_rules',
        'created_at',
        server_default=sa.text('now()'),
    )
    op.alter_column(
        'table_combination_rules',
        'updated_at',
        server_default=sa.text('now()'),
    )


def downgrade() -> None:
    op.alter_column(
        'table_combination_rules',
        'created_at',
        server_default=None,
    )
    op.alter_column(
        'table_combination_rules',
        'updated_at',
        server_default=None,
    )
