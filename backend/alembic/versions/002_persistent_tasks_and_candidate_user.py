"""Persist analysis tasks and link candidates to users.

Revision ID: 002_tasks_candidate_user
Revises: 001_initial_schema
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "002_tasks_candidate_user"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("candidates", sa.Column("user_id", sa.Integer(), nullable=True))

    op.execute(
        """
        UPDATE candidates c
        JOIN (
            SELECT MIN(c2.id) AS candidate_id, u.id AS user_id
            FROM candidates c2
            JOIN users u ON LOWER(c2.email) = LOWER(u.email)
            WHERE u.role = 'candidate'
            GROUP BY u.id
        ) matched ON matched.candidate_id = c.id
        SET c.user_id = matched.user_id
        WHERE c.user_id IS NULL
        """
    )

    op.create_unique_constraint("uq_candidates_user_id", "candidates", ["user_id"])
    op.create_foreign_key(
        "fk_candidates_user_id_users",
        "candidates",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute("UPDATE applications SET status = 'not-reviewed' WHERE status IS NULL OR status = ''")
    op.alter_column(
        "applications",
        "status",
        existing_type=sa.String(length=50),
        nullable=False,
        server_default="not-reviewed",
    )

    op.create_table(
        "analysis_tasks",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="running"),
        sa.Column("progress", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("message", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analysis_tasks_job_id"), "analysis_tasks", ["job_id"], unique=False)
    op.create_index(op.f("ix_analysis_tasks_user_id"), "analysis_tasks", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_analysis_tasks_user_id"), table_name="analysis_tasks")
    op.drop_index(op.f("ix_analysis_tasks_job_id"), table_name="analysis_tasks")
    op.drop_table("analysis_tasks")

    op.alter_column(
        "applications",
        "status",
        existing_type=sa.String(length=50),
        nullable=True,
        server_default=None,
    )

    op.drop_constraint("fk_candidates_user_id_users", "candidates", type_="foreignkey")
    op.drop_constraint("uq_candidates_user_id", "candidates", type_="unique")
    op.drop_column("candidates", "user_id")
