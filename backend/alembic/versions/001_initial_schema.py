"""Initial schema baseline.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-07-14
"""

from alembic import op
import sqlalchemy as sa


revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_id"), "users", ["id"], unique=False)

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidates_email"), "candidates", ["email"], unique=False)
    op.create_index(op.f("ix_candidates_id"), "candidates", ["id"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("job_title", sa.String(length=150), nullable=False),
        sa.Column("short_description", sa.String(length=255), nullable=True),
        sa.Column("job_link", sa.String(length=255), nullable=True),
        sa.Column("salary_range", sa.String(length=50), nullable=True),
        sa.Column("salary_currency", sa.String(length=5), nullable=True),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("variable_min", sa.Integer(), nullable=True),
        sa.Column("variable_max", sa.Integer(), nullable=True),
        sa.Column("location", sa.String(length=100), nullable=True),
        sa.Column("job_description", sa.Text(), nullable=True),
        sa.Column("additional_preferences", sa.Text(), nullable=True),
        sa.Column("non_negotiables", sa.Text(), nullable=True),
        sa.Column("opportunity_type", sa.String(length=20), nullable=True),
        sa.Column("min_experience_years", sa.Integer(), nullable=True),
        sa.Column("job_type", sa.String(length=20), nullable=True),
        sa.Column("job_site", sa.String(length=20), nullable=True),
        sa.Column("openings", sa.Integer(), nullable=True),
        sa.Column("perks", sa.Text(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration", sa.String(length=100), nullable=True),
        sa.Column("apply_by", sa.DateTime(timezone=True), nullable=True),
        sa.Column("required_skills", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("draft_data", sa.Text(), nullable=True),
        sa.Column("draft_step", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_id"), "jobs", ["id"], unique=False)
    op.create_index("ix_jobs_user_status_created", "jobs", ["user_id", "status", "created_at"], unique=False)

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("stored_filename", sa.String(length=255), nullable=True),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=120), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("extracted_text", sa.Text(), nullable=True),
        sa.Column("raw_extracted_text", sa.Text(), nullable=True),
        sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("extraction_metadata_json", sa.Text(), nullable=True),
        sa.Column("structured_json", sa.Text(), nullable=True),
        sa.Column("structured_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ai_structured_json", sa.Text(), nullable=True),
        sa.Column("ai_structured_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("ai_model", sa.String(length=120), nullable=True),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_warnings", sa.Text(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_id"), "resumes", ["id"], unique=False)
    op.create_index("ix_resumes_candidate_created", "resumes", ["candidate_id", "created_at"], unique=False)

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("candidate_id", sa.Integer(), nullable=True),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("ai_explanation", sa.Text(), nullable=True),
        sa.Column("semantic_score", sa.Float(), nullable=True),
        sa.Column("skills_score", sa.Float(), nullable=True),
        sa.Column("experience_score", sa.Float(), nullable=True),
        sa.Column("ai_score", sa.Float(), nullable=True),
        sa.Column("final_score", sa.Integer(), nullable=True),
        sa.Column("score_breakdown_json", sa.Text(), nullable=True),
        sa.Column("matched_skills_json", sa.Text(), nullable=True),
        sa.Column("missing_skills_json", sa.Text(), nullable=True),
        sa.Column("ranking_explanation", sa.Text(), nullable=True),
        sa.Column("score_updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.id"]),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "job_id", name="uq_applications_candidate_job"),
    )
    op.create_index(op.f("ix_applications_id"), "applications", ["id"], unique=False)
    op.create_index("ix_applications_candidate_created", "applications", ["candidate_id", "created_at"], unique=False)
    op.create_index("ix_applications_job_final_score", "applications", ["job_id", "final_score"], unique=False)

    op.create_table(
        "embeddings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=20), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=False),
        sa.Column("dim", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column("vector_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_type", "entity_id", "model", "text_hash", name="uq_embeddings_entity_model_hash"),
    )
    op.create_index(op.f("ix_embeddings_id"), "embeddings", ["id"], unique=False)
    op.create_index("ix_embeddings_lookup", "embeddings", ["entity_type", "entity_id", "model"], unique=False)

    op.create_table(
        "ai_resume_analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("candidate_summary", sa.Text(), nullable=False),
        sa.Column("strengths_json", sa.Text(), nullable=False),
        sa.Column("weaknesses_json", sa.Text(), nullable=False),
        sa.Column("strength_reasoning", sa.Text(), nullable=True),
        sa.Column("weakness_reasoning", sa.Text(), nullable=True),
        sa.Column("matched_skills_json", sa.Text(), nullable=False),
        sa.Column("missing_skills_json", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False, server_default="gemini"),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="success"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("application_id", name="uq_ai_resume_analysis_application"),
    )
    op.create_index(op.f("ix_ai_resume_analyses_id"), "ai_resume_analyses", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_ai_resume_analyses_id"), table_name="ai_resume_analyses")
    op.drop_table("ai_resume_analyses")
    op.drop_index("ix_embeddings_lookup", table_name="embeddings")
    op.drop_index(op.f("ix_embeddings_id"), table_name="embeddings")
    op.drop_table("embeddings")
    op.drop_index("ix_applications_job_final_score", table_name="applications")
    op.drop_index("ix_applications_candidate_created", table_name="applications")
    op.drop_index(op.f("ix_applications_id"), table_name="applications")
    op.drop_table("applications")
    op.drop_index("ix_resumes_candidate_created", table_name="resumes")
    op.drop_index(op.f("ix_resumes_id"), table_name="resumes")
    op.drop_table("resumes")
    op.drop_index("ix_jobs_user_status_created", table_name="jobs")
    op.drop_index(op.f("ix_jobs_id"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_candidates_id"), table_name="candidates")
    op.drop_index(op.f("ix_candidates_email"), table_name="candidates")
    op.drop_table("candidates")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
