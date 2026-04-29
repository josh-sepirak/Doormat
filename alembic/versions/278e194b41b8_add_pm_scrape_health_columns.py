"""add_pm_scrape_health_columns

Revision ID: 278e194b41b8
Revises: c7e8f9a0b1c2
Create Date: 2026-04-26 20:29:49.114891

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '278e194b41b8'
down_revision: Union[str, Sequence[str], None] = 'c7e8f9a0b1c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('property_managers', sa.Column('last_fetch_attempted_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('property_managers', sa.Column('last_fetch_error', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('property_managers') as batch_op:
        batch_op.drop_column('last_fetch_error')
        batch_op.drop_column('last_fetch_attempted_at')
