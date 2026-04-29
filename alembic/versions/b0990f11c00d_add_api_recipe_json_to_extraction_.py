"""add_api_recipe_json_to_extraction_strategies

Revision ID: b0990f11c00d
Revises: d5e6f7a8b9c0
Create Date: 2026-04-29 16:37:29.095304

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0990f11c00d'
down_revision: Union[str, Sequence[str], None] = 'd5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add api_recipe_json column to extraction_strategies
    with op.batch_alter_table('extraction_strategies') as batch_op:
        batch_op.add_column(sa.Column('api_recipe_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # Drop api_recipe_json column
    with op.batch_alter_table('extraction_strategies') as batch_op:
        batch_op.drop_column('api_recipe_json')
