"""add listing coords, preference prompt_overrides, geocode_cache

Revision ID: c7e8f9a0b1c2
Revises: f2c809279f73
Create Date: 2026-04-26

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7e8f9a0b1c2"
down_revision: Union[str, Sequence[str], None] = "f2c809279f73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    listing_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(listings)"))}
    with op.batch_alter_table("listings") as batch_op:
        if "latitude" not in listing_cols:
            batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
        if "longitude" not in listing_cols:
            batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))

    pref_cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(preferences)"))}
    if "prompt_overrides" not in pref_cols:
        with op.batch_alter_table("preferences") as batch_op:
            batch_op.add_column(sa.Column("prompt_overrides", sa.Text(), nullable=True))

    tables = {row[0] for row in conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='table'"))}
    if "geocode_cache" not in tables:
        op.create_table(
            "geocode_cache",
            sa.Column("cache_key", sa.String(length=64), nullable=False),
            sa.Column("query_text", sa.String(length=512), nullable=False),
            sa.Column("latitude", sa.Float(), nullable=False),
            sa.Column("longitude", sa.Float(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("cache_key"),
        )


def downgrade() -> None:
    op.drop_table("geocode_cache")
    with op.batch_alter_table("preferences") as batch_op:
        batch_op.drop_column("prompt_overrides")
    with op.batch_alter_table("listings") as batch_op:
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
