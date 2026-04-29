"""add_sources_enabled_and_source

Revision ID: f2c809279f73
Revises: 8f1a2c3d4b5e
Create Date: 2026-04-26 12:15:02.454634

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f2c809279f73'
down_revision: Union[str, Sequence[str], None] = '8f1a2c3d4b5e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    listing_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(listings)"))}
    if 'source' not in listing_cols:
        with op.batch_alter_table('listings') as batch_op:
            batch_op.add_column(
                sa.Column('source', sa.String(length=50), nullable=False, server_default='pm_direct')
            )

    pref_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(preferences)"))}
    if 'sources_enabled' not in pref_cols:
        with op.batch_alter_table('preferences') as batch_op:
            batch_op.add_column(
                sa.Column('sources_enabled', sa.Text(), nullable=False, server_default='["craigslist"]')
            )


def downgrade() -> None:
    with op.batch_alter_table('preferences') as batch_op:
        batch_op.drop_column('sources_enabled')
    with op.batch_alter_table('listings') as batch_op:
        batch_op.drop_column('source')
