import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .api import auth as auth_api
from .api import job as job_api
from .database import engine, init_db
from .utils.error_handlers import get_error_message
from .services.application_service import backfill_missing_application_scores

app = FastAPI(title="AI Resume Skill Analyzer")

app.include_router(auth_api.router)
app.include_router(job_api.router)

logger = logging.getLogger(__name__)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTPException with user-friendly messages."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "status_code": exc.status_code,
        },
    )


@app.exception_handler(OperationalError)
async def sqlalchemy_operational_error_handler(request: Request, exc: OperationalError):
    """Handle database operational errors."""
    logger.exception("Database OperationalError: %s", exc)
    root = getattr(exc, "orig", None)
    root_msg = str(root) if root else str(exc)
    return JSONResponse(
        status_code=503,
        content={
            "success": False,
            "error": get_error_message("database_error"),
            "details": f"Database operation failed. Check DATABASE_URL / DB server. Details: {root_msg}",
        },
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Handle general database errors."""
    logger.exception("Database SQLAlchemyError: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": get_error_message("database_error"),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors globally."""
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": get_error_message("server_error"),
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle ValueError with user-friendly message."""
    logger.warning("ValueError: %s", exc)
    return JSONResponse(
        status_code=400,
        content={
            "success": False,
            "error": str(exc) or get_error_message("validation_error"),
        },
    )


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "Backend running",
        "service": "AI Resume Skill Analyzer"
    }


_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=[*_default_origins, *_extra_origins],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    try:
        init_db()

        dialect = (getattr(engine, "dialect", None) and engine.dialect.name) or ""
        dialect = str(dialect).lower()

        if dialect == "sqlite":
            raise RuntimeError("SQLite is no longer supported. Configure a MySQL DATABASE_URL.")

        if dialect and dialect != "mysql":
            raise RuntimeError(f"Unsupported database dialect '{dialect}'. This backend now requires MySQL.")

        # Ensure the existing MySQL schema supports candidate accounts.
        # Many starter schemas define `users.role` as ENUM('admin','recruiter') only.
        if dialect == "mysql":
            try:
                with engine.begin() as conn:
                    row = conn.execute(
                        text(
                            """
                            SELECT COLUMN_TYPE
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'users'
                              AND COLUMN_NAME = 'role'
                            """
                        )
                    ).fetchone()

                    column_type = (row[0] if row else "") or ""
                    if "enum" in column_type.lower() and "candidate" not in column_type.lower():
                        # Keep NULL/default behavior consistent with the existing column.
                        conn.execute(
                            text(
                                "ALTER TABLE users MODIFY COLUMN role "
                                "ENUM('admin','recruiter','candidate') NULL DEFAULT 'recruiter'"
                            )
                        )
            except Exception:
                # Best-effort only. If the DB user doesn't have ALTER privileges, the
                # auth endpoint will return a clear message instructing what to run.
                pass

        # Ensure jobs support drafts via a status column.
        # Add: jobs.status ENUM('active','draft','closed') NOT NULL DEFAULT 'active'
        if dialect == "mysql":
            try:
                with engine.begin() as conn:
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'jobs'
                              AND COLUMN_NAME = 'status'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(
                            text(
                                "ALTER TABLE jobs "
                                "ADD COLUMN status ENUM('active','draft','closed') "
                                "NOT NULL DEFAULT 'active'"
                            )
                        )
                    else:
                        row = conn.execute(
                            text(
                                """
                                SELECT COLUMN_TYPE
                                FROM information_schema.COLUMNS
                                WHERE TABLE_SCHEMA = DATABASE()
                                  AND TABLE_NAME = 'jobs'
                                  AND COLUMN_NAME = 'status'
                                """
                            )
                        ).fetchone()
                        column_type = (row[0] if row else "") or ""
                        if "enum" in column_type.lower() and "deleted" not in column_type.lower():
                            conn.execute(
                                text(
                                    "ALTER TABLE jobs MODIFY COLUMN status "
                                    "ENUM('active','draft','closed','deleted') "
                                    "NOT NULL DEFAULT 'active'"
                                )
                            )
            except Exception:
                # Best-effort only; endpoints will still work but won't be able to persist drafts.
                pass

        # Persist draft form state (JSON string) + current step for resumable drafts.
        if dialect == "mysql":
            try:
                with engine.begin() as conn:
                    # jobs.draft_data (TEXT)
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'jobs'
                              AND COLUMN_NAME = 'draft_data'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE jobs ADD COLUMN draft_data TEXT NULL"))

                    # jobs.draft_step (INT)
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'jobs'
                              AND COLUMN_NAME = 'draft_step'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE jobs ADD COLUMN draft_step INT NOT NULL DEFAULT 1"))
            except Exception:
                pass

        # Ensure resumes table supports metadata columns used by upload/apply flows.
        if dialect == "mysql":
            try:
                with engine.begin() as conn:
                    # embeddings table (Module 9)
                    try:
                        conn.execute(
                            text(
                                """
                                CREATE TABLE IF NOT EXISTS embeddings (
                                    id INT AUTO_INCREMENT PRIMARY KEY,
                                    entity_type VARCHAR(20) NOT NULL,
                                    entity_id INT NOT NULL,
                                    model VARCHAR(120) NOT NULL,
                                    dim INT NOT NULL DEFAULT 0,
                                    text_hash VARCHAR(64) NOT NULL,
                                    vector_json LONGTEXT NOT NULL,
                                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                                    UNIQUE KEY uq_embeddings_entity_model_hash (entity_type, entity_id, model, text_hash),
                                    KEY ix_embeddings_lookup (entity_type, entity_id, model)
                                )
                                """
                            )
                        )
                    except Exception:
                        pass

                    # resumes.stored_filename
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'stored_filename'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN stored_filename VARCHAR(255) NULL"))

                    # resumes.original_filename
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'original_filename'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN original_filename VARCHAR(255) NULL"))

                    # resumes.content_type
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'content_type'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN content_type VARCHAR(120) NULL"))

                    # resumes.size_bytes
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'size_bytes'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN size_bytes INT NOT NULL DEFAULT 0"))

                    # resumes.extracted_text
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'extracted_text'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN extracted_text TEXT NULL"))

                    # resumes.raw_extracted_text
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'raw_extracted_text'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN raw_extracted_text TEXT NULL"))

                    # resumes.extraction_status
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'extraction_status'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN extraction_status VARCHAR(32) NOT NULL DEFAULT 'pending'"))

                    # resumes.extraction_metadata_json
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'extraction_metadata_json'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN extraction_metadata_json TEXT NULL"))

                    # resumes.structured_json
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'structured_json'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN structured_json TEXT NULL"))

                    # resumes.structured_version
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'structured_version'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN structured_version INT NOT NULL DEFAULT 1"))

                    # resumes.ai_structured_json
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'ai_structured_json'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN ai_structured_json TEXT NULL"))

                    # resumes.ai_structured_version
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'ai_structured_version'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN ai_structured_version INT NOT NULL DEFAULT 1"))

                    # resumes.ai_model
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'ai_model'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN ai_model VARCHAR(120) NULL"))

                    # resumes.ai_generated_at
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'ai_generated_at'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN ai_generated_at DATETIME NULL"))

                    # resumes.ai_warnings
                    row = conn.execute(
                        text(
                            """
                            SELECT COUNT(*)
                            FROM information_schema.COLUMNS
                            WHERE TABLE_SCHEMA = DATABASE()
                              AND TABLE_NAME = 'resumes'
                              AND COLUMN_NAME = 'ai_warnings'
                            """
                        )
                    ).fetchone()
                    exists = int(row[0]) if row else 0
                    if exists == 0:
                        conn.execute(text("ALTER TABLE resumes ADD COLUMN ai_warnings TEXT NULL"))
            except Exception:
                pass

        # Ensure applications table supports apply/analyze columns on MySQL too.
        if dialect == "mysql":
            try:
                with engine.begin() as conn:
                    def _mysql_add_column_if_missing(*, table: str, column: str, ddl: str) -> None:
                        row = conn.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM information_schema.COLUMNS
                                WHERE TABLE_SCHEMA = DATABASE()
                                  AND TABLE_NAME = :table
                                  AND COLUMN_NAME = :column
                                """
                            ),
                            {"table": table, "column": column},
                        ).fetchone()
                        exists = int(row[0]) if row else 0
                        if exists == 0:
                            conn.execute(text(ddl))

                    def _mysql_add_index_if_missing(*, table: str, index: str, ddl: str) -> None:
                        row = conn.execute(
                            text(
                                """
                                SELECT COUNT(*)
                                FROM information_schema.STATISTICS
                                WHERE TABLE_SCHEMA = DATABASE()
                                  AND TABLE_NAME = :table
                                  AND INDEX_NAME = :index
                                """
                            ),
                            {"table": table, "index": index},
                        ).fetchone()
                        exists = int(row[0]) if row else 0
                        if exists == 0:
                            conn.execute(text(ddl))

                    _mysql_add_column_if_missing(
                        table="applications",
                        column="resume_id",
                        ddl="ALTER TABLE applications ADD COLUMN resume_id INT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="ai_explanation",
                        ddl="ALTER TABLE applications ADD COLUMN ai_explanation TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="status",
                        ddl="ALTER TABLE applications ADD COLUMN status VARCHAR(50) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="semantic_score",
                        ddl="ALTER TABLE applications ADD COLUMN semantic_score DOUBLE NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="skills_score",
                        ddl="ALTER TABLE applications ADD COLUMN skills_score DOUBLE NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="experience_score",
                        ddl="ALTER TABLE applications ADD COLUMN experience_score DOUBLE NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="ai_score",
                        ddl="ALTER TABLE applications ADD COLUMN ai_score DOUBLE NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="final_score",
                        ddl="ALTER TABLE applications ADD COLUMN final_score INT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="score_breakdown_json",
                        ddl="ALTER TABLE applications ADD COLUMN score_breakdown_json TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="score_updated_at",
                        ddl="ALTER TABLE applications ADD COLUMN score_updated_at DATETIME NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="matched_skills_json",
                        ddl="ALTER TABLE applications ADD COLUMN matched_skills_json TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="missing_skills_json",
                        ddl="ALTER TABLE applications ADD COLUMN missing_skills_json TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="ranking_explanation",
                        ddl="ALTER TABLE applications ADD COLUMN ranking_explanation TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="ai_resume_analyses",
                        column="strength_reasoning",
                        ddl="ALTER TABLE ai_resume_analyses ADD COLUMN strength_reasoning TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="ai_resume_analyses",
                        column="weakness_reasoning",
                        ddl="ALTER TABLE ai_resume_analyses ADD COLUMN weakness_reasoning TEXT NULL",
                    )
                    _mysql_add_index_if_missing(
                        table="jobs",
                        index="ix_jobs_user_status_created",
                        ddl="CREATE INDEX ix_jobs_user_status_created ON jobs (user_id, status, created_at)",
                    )
                    _mysql_add_index_if_missing(
                        table="resumes",
                        index="ix_resumes_candidate_created",
                        ddl="CREATE INDEX ix_resumes_candidate_created ON resumes (candidate_id, created_at)",
                    )
                    _mysql_add_index_if_missing(
                        table="applications",
                        index="ix_applications_job_final_score",
                        ddl="CREATE INDEX ix_applications_job_final_score ON applications (job_id, final_score)",
                    )
                    _mysql_add_index_if_missing(
                        table="applications",
                        index="ix_applications_candidate_created",
                        ddl="CREATE INDEX ix_applications_candidate_created ON applications (candidate_id, created_at)",
                    )
                from .database import SessionLocal
                with SessionLocal() as db:
                    backfill_missing_application_scores(db)
            except Exception:
                pass

        app.state.db_init_error = None
    except Exception as e:
        app.state.db_init_error = str(e)


@app.get("/db/health")
def db_health():
    if getattr(app.state, "db_init_error", None):
        raise HTTPException(
            status_code=503,
            detail=f"DB init failed: {app.state.db_init_error}",
        )

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"DB connection failed: {e}",
        )

    return {"status": "ok"}
