"""add projects and clarification workflow

Revision ID: 20260424_0004
Revises: 20260423_0003
Create Date: 2026-04-24 11:55:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "20260424_0004"
down_revision: str | None = "20260423_0003"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("repository_url", sa.Text(), nullable=True),
        sa.Column("archive_reference", sa.Text(), nullable=True),
        sa.Column("ingestion_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("ingestion_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column("analysis_runs", sa.Column("project_id", sa.Uuid(), nullable=True))
    op.add_column("analysis_runs", sa.Column("task_type", sa.String(length=40), nullable=False, server_default="feature"))
    op.add_column("analysis_runs", sa.Column("input_type", sa.String(length=40), nullable=False, server_default="text"))
    op.add_column("analysis_runs", sa.Column("input_text", sa.Text(), nullable=False, server_default=""))
    op.add_column("analysis_runs", sa.Column("input_file_reference", sa.Text(), nullable=True))
    op.add_column("analysis_runs", sa.Column("clarification_payload", sa.JSON(), nullable=False, server_default="{}"))
    op.create_index(op.f("ix_analysis_runs_project_id"), "analysis_runs", ["project_id"], unique=False)
    op.create_foreign_key(
        "fk_analysis_runs_project_id_projects",
        "analysis_runs",
        "projects",
        ["project_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_table(
        "clarification_rounds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("round_index", sa.Integer(), nullable=False),
        sa.Column("questions", sa.JSON(), nullable=False),
        sa.Column("answers", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["analysis_run_id"], ["analysis_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_clarification_rounds_analysis_run_id"), "clarification_rounds", ["analysis_run_id"], unique=False)
    op.alter_column("analysis_runs", "task_type", server_default=None)
    op.alter_column("analysis_runs", "input_type", server_default=None)
    op.alter_column("analysis_runs", "input_text", server_default=None)
    op.alter_column("analysis_runs", "clarification_payload", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_clarification_rounds_analysis_run_id"), table_name="clarification_rounds")
    op.drop_table("clarification_rounds")
    op.drop_constraint("fk_analysis_runs_project_id_projects", "analysis_runs", type_="foreignkey")
    op.drop_index(op.f("ix_analysis_runs_project_id"), table_name="analysis_runs")
    op.drop_column("analysis_runs", "clarification_payload")
    op.drop_column("analysis_runs", "input_file_reference")
    op.drop_column("analysis_runs", "input_text")
    op.drop_column("analysis_runs", "input_type")
    op.drop_column("analysis_runs", "task_type")
    op.drop_column("analysis_runs", "project_id")
    op.drop_table("projects")
