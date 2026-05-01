"""add trusted_sources table

Revision ID: e1a2b3c4d5e6
Revises: b0990f11c00d
Create Date: 2026-05-01

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e1a2b3c4d5e6"
down_revision: Union[str, Sequence[str], None] = "b0990f11c00d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "trusted_sources",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=True),
        sa.Column("linked_property_manager_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["linked_property_manager_id"],
            ["property_managers.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kind", "url", name="uq_trusted_source_kind_url"),
    )
    op.create_index(op.f("ix_trusted_sources_kind"), "trusted_sources", ["kind"], unique=False)
    op.create_index(op.f("ix_trusted_sources_city"), "trusted_sources", ["city"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_trusted_sources_city"), table_name="trusted_sources")
    op.drop_index(op.f("ix_trusted_sources_kind"), table_name="trusted_sources")
    op.drop_table("trusted_sources")
