"""add search runs events and listing results

Revision ID: 8f1a2c3d4b5e
Revises: 4070433b0e60
Create Date: 2026-04-26

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "8f1a2c3d4b5e"
down_revision: Union[str, Sequence[str], None] = "4070433b0e60"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("discovery_run_id", sa.String(length=36), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("preference_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("current_stage", sa.String(length=64), nullable=False),
        sa.Column("cancel_requested", sa.Boolean(), nullable=False),
        sa.Column("sources_checked", sa.Integer(), nullable=False),
        sa.Column("managers_validated", sa.Integer(), nullable=False),
        sa.Column("listings_seen", sa.Integer(), nullable=False),
        sa.Column("great_matches", sa.Integer(), nullable=False),
        sa.Column("worth_a_look", sa.Integer(), nullable=False),
        sa.Column("near_misses", sa.Integer(), nullable=False),
        sa.Column("filtered_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd_so_far", sa.Float(), nullable=False),
        sa.Column("active_revision", sa.Integer(), nullable=False),
        sa.Column("filters_json", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["discovery_run_id"],
            ["discovery_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discovery_run_id"),
    )
    op.create_index("idx_search_run_status_started", "search_runs", ["status", "started_at"])
    op.create_index(op.f("ix_search_runs_city"), "search_runs", ["city"])
    op.create_index(op.f("ix_search_runs_preference_id"), "search_runs", ["preference_id"])
    op.create_index(op.f("ix_search_runs_started_at"), "search_runs", ["started_at"])
    op.create_index(op.f("ix_search_runs_status"), "search_runs", ["status"])
    op.create_index(op.f("ix_search_runs_discovery_run_id"), "search_runs", ["discovery_run_id"])

    op.create_table(
        "search_run_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["search_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_search_run_event_run_seq", "search_run_events", ["run_id", "sequence"])
    op.create_index(op.f("ix_search_run_events_event_type"), "search_run_events", ["event_type"])
    op.create_index(op.f("ix_search_run_events_timestamp"), "search_run_events", ["timestamp"])
    op.create_index(op.f("ix_search_run_events_run_id"), "search_run_events", ["run_id"])

    op.create_table(
        "run_listing_results",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("listing_id", sa.String(length=36), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("filter_reasons_json", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
        ),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["search_runs.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "listing_id", "revision", name="uq_run_listing_revision"),
    )
    op.create_index("idx_run_listing_result_run_rev", "run_listing_results", ["run_id", "revision"])
    op.create_index("idx_run_listing_result_run_cat", "run_listing_results", ["run_id", "category"])
    op.create_index(op.f("ix_run_listing_results_category"), "run_listing_results", ["category"])
    op.create_index(op.f("ix_run_listing_results_run_id"), "run_listing_results", ["run_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_run_listing_results_run_id"), table_name="run_listing_results")
    op.drop_index(op.f("ix_run_listing_results_category"), table_name="run_listing_results")
    op.drop_index("idx_run_listing_result_run_cat", table_name="run_listing_results")
    op.drop_index("idx_run_listing_result_run_rev", table_name="run_listing_results")
    op.drop_table("run_listing_results")

    op.drop_index(op.f("ix_search_run_events_run_id"), table_name="search_run_events")
    op.drop_index(op.f("ix_search_run_events_timestamp"), table_name="search_run_events")
    op.drop_index(op.f("ix_search_run_events_event_type"), table_name="search_run_events")
    op.drop_index("idx_search_run_event_run_seq", table_name="search_run_events")
    op.drop_table("search_run_events")

    op.drop_index(op.f("ix_search_runs_discovery_run_id"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_status"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_started_at"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_preference_id"), table_name="search_runs")
    op.drop_index(op.f("ix_search_runs_city"), table_name="search_runs")
    op.drop_index("idx_search_run_status_started", table_name="search_runs")
    op.drop_table("search_runs")
