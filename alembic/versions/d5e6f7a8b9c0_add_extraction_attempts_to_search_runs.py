"""add extraction_attempts to search_runs

Revision ID: d5e6f7a8b9c0
Revises: 278e194b41b8
Create Date: 2026-04-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: Union[str, Sequence[str], None] = "278e194b41b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("search_runs") as batch_op:
        batch_op.add_column(
            sa.Column(
                "extraction_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("search_runs") as batch_op:
        batch_op.drop_column("extraction_attempts")
