"""add review fields to analysis runs

Revision ID: 20260423_0003
Revises: 20260423_0002
Create Date: 2026-04-23 21:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260423_0003"
down_revision: str | None = "20260423_0002"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "analysis_runs",
        sa.Column("review_status", sa.String(length=32), nullable=False, server_default="draft"),
    )
    op.add_column(
        "analysis_runs",
        sa.Column("reviewer_note", sa.Text(), nullable=False, server_default=""),
    )
    op.alter_column("analysis_runs", "review_status", server_default=None)
    op.alter_column("analysis_runs", "reviewer_note", server_default=None)


def downgrade() -> None:
    op.drop_column("analysis_runs", "reviewer_note")
    op.drop_column("analysis_runs", "review_status")
