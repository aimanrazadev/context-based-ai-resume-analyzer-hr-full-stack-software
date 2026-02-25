import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .api import auth as auth_api
from .api import interview as interview_api
from .api import job as job_api
from .api import resume as resume_api
from .database import engine, init_db
from .utils.error_handlers import get_error_message

app = FastAPI(title="AI Resume Skill Analyzer")

app.include_router(auth_api.router)
app.include_router(job_api.router)
app.include_router(resume_api.router)
app.include_router(interview_api.router)

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

        # SQLite dev mode: create_all() does not add columns to existing tables.
        # So we do a tiny best-effort migration for columns we rely on.
        if dialect == "sqlite":
            try:
                with engine.begin() as conn:
                    def _sqlite_has_column(table: str, column: str) -> bool:
                        rows = conn.exec_driver_sql(f"PRAGMA table_info({table})").fetchall()
                        return any((r[1] == column) for r in rows)  # r[1] = name

                    def _sqlite_add_column_if_missing(*, table: str, column: str, ddl: str) -> None:
                        if not _sqlite_has_column(table, column):
                            conn.exec_driver_sql(ddl)

                    # embeddings table (Module 9)
                    conn.exec_driver_sql(
                        """
                        CREATE TABLE IF NOT EXISTS embeddings (
                            id INTEGER PRIMARY KEY,
                            entity_type VARCHAR(20) NOT NULL,
                            entity_id INTEGER NOT NULL,
                            model VARCHAR(120) NOT NULL,
                            dim INTEGER NOT NULL DEFAULT 0,
                            text_hash VARCHAR(64) NOT NULL,
                            vector_json TEXT NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        )
                        """
                    )
                    # Best-effort indexes (SQLite will ignore if already exists)
                    try:
                        conn.exec_driver_sql(
                            "CREATE INDEX IF NOT EXISTS ix_embeddings_lookup ON embeddings(entity_type, entity_id, model)"
                        )
                    except Exception:
                        pass

                    # jobs: drafts/status support
                    _sqlite_add_column_if_missing(
                        table="jobs",
                        column="status",
                        ddl="ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
                    )
                    _sqlite_add_column_if_missing(
                        table="jobs",
                        column="draft_data",
                        ddl="ALTER TABLE jobs ADD COLUMN draft_data TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="jobs",
                        column="draft_step",
                        ddl="ALTER TABLE jobs ADD COLUMN draft_step INTEGER NOT NULL DEFAULT 1",
                    )

                    # resumes: metadata used by upload/apply flows
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="stored_filename",
                        ddl="ALTER TABLE resumes ADD COLUMN stored_filename VARCHAR(255) NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="original_filename",
                        ddl="ALTER TABLE resumes ADD COLUMN original_filename VARCHAR(255) NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="content_type",
                        ddl="ALTER TABLE resumes ADD COLUMN content_type VARCHAR(120) NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="size_bytes",
                        ddl="ALTER TABLE resumes ADD COLUMN size_bytes INTEGER NOT NULL DEFAULT 0",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="extracted_text",
                        ddl="ALTER TABLE resumes ADD COLUMN extracted_text TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="structured_json",
                        ddl="ALTER TABLE resumes ADD COLUMN structured_json TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="structured_version",
                        ddl="ALTER TABLE resumes ADD COLUMN structured_version INTEGER NOT NULL DEFAULT 1",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="ai_structured_json",
                        ddl="ALTER TABLE resumes ADD COLUMN ai_structured_json TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="ai_structured_version",
                        ddl="ALTER TABLE resumes ADD COLUMN ai_structured_version INTEGER NOT NULL DEFAULT 1",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="ai_model",
                        ddl="ALTER TABLE resumes ADD COLUMN ai_model VARCHAR(120) NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="ai_generated_at",
                        ddl="ALTER TABLE resumes ADD COLUMN ai_generated_at DATETIME NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="resumes",
                        column="ai_warnings",
                        ddl="ALTER TABLE resumes ADD COLUMN ai_warnings TEXT NULL",
                    )

                    # applications: fields used by apply/analyze flow
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="resume_id",
                        ddl="ALTER TABLE applications ADD COLUMN resume_id INTEGER NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="match_score",
                        ddl="ALTER TABLE applications ADD COLUMN match_score REAL NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="ai_explanation",
                        ddl="ALTER TABLE applications ADD COLUMN ai_explanation TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="status",
                        ddl="ALTER TABLE applications ADD COLUMN status TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="semantic_score",
                        ddl="ALTER TABLE applications ADD COLUMN semantic_score REAL NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="skills_score",
                        ddl="ALTER TABLE applications ADD COLUMN skills_score REAL NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="final_score",
                        ddl="ALTER TABLE applications ADD COLUMN final_score INTEGER NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="score_breakdown_json",
                        ddl="ALTER TABLE applications ADD COLUMN score_breakdown_json TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="applications",
                        column="score_updated_at",
                        ddl="ALTER TABLE applications ADD COLUMN score_updated_at DATETIME NULL",
                    )

                    # interviews: Module 11 interview engine fields
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="status",
                        ddl="ALTER TABLE interviews ADD COLUMN status TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="updated_at",
                        ddl="ALTER TABLE interviews ADD COLUMN updated_at DATETIME NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="scheduled_at",
                        ddl="ALTER TABLE interviews ADD COLUMN scheduled_at DATETIME NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="timezone",
                        ddl="ALTER TABLE interviews ADD COLUMN timezone TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="duration_minutes",
                        ddl="ALTER TABLE interviews ADD COLUMN duration_minutes INTEGER NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="mode",
                        ddl="ALTER TABLE interviews ADD COLUMN mode TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="meeting_link",
                        ddl="ALTER TABLE interviews ADD COLUMN meeting_link TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="location",
                        ddl="ALTER TABLE interviews ADD COLUMN location TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="interviewer_name",
                        ddl="ALTER TABLE interviews ADD COLUMN interviewer_name TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="recruiter_notes",
                        ddl="ALTER TABLE interviews ADD COLUMN recruiter_notes TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="feedback",
                        ddl="ALTER TABLE interviews ADD COLUMN feedback TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="outcome",
                        ddl="ALTER TABLE interviews ADD COLUMN outcome TEXT NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="completed_at",
                        ddl="ALTER TABLE interviews ADD COLUMN completed_at DATETIME NULL",
                    )
                    _sqlite_add_column_if_missing(
                        table="interviews",
                        column="evaluated_at",
                        ddl="ALTER TABLE interviews ADD COLUMN evaluated_at DATETIME NULL",
                    )
            except Exception:
                # Best-effort only. If the SQLite file is read-only or the table doesn't exist yet,
                # the app can still boot and the /db/health endpoint will help debug.
                pass

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

                    _mysql_add_column_if_missing(
                        table="applications",
                        column="resume_id",
                        ddl="ALTER TABLE applications ADD COLUMN resume_id INT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="applications",
                        column="match_score",
                        ddl="ALTER TABLE applications ADD COLUMN match_score DOUBLE NULL",
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

                    # interviews: Module 11 interview engine fields
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="status",
                        ddl="ALTER TABLE interviews ADD COLUMN status VARCHAR(32) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="updated_at",
                        ddl="ALTER TABLE interviews ADD COLUMN updated_at DATETIME NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="scheduled_at",
                        ddl="ALTER TABLE interviews ADD COLUMN scheduled_at DATETIME NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="timezone",
                        ddl="ALTER TABLE interviews ADD COLUMN timezone VARCHAR(64) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="duration_minutes",
                        ddl="ALTER TABLE interviews ADD COLUMN duration_minutes INT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="mode",
                        ddl="ALTER TABLE interviews ADD COLUMN mode VARCHAR(32) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="meeting_link",
                        ddl="ALTER TABLE interviews ADD COLUMN meeting_link VARCHAR(500) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="location",
                        ddl="ALTER TABLE interviews ADD COLUMN location VARCHAR(255) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="interviewer_name",
                        ddl="ALTER TABLE interviews ADD COLUMN interviewer_name VARCHAR(120) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="recruiter_notes",
                        ddl="ALTER TABLE interviews ADD COLUMN recruiter_notes TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="feedback",
                        ddl="ALTER TABLE interviews ADD COLUMN feedback TEXT NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="outcome",
                        ddl="ALTER TABLE interviews ADD COLUMN outcome VARCHAR(32) NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="completed_at",
                        ddl="ALTER TABLE interviews ADD COLUMN completed_at DATETIME NULL",
                    )
                    _mysql_add_column_if_missing(
                        table="interviews",
                        column="evaluated_at",
                        ddl="ALTER TABLE interviews ADD COLUMN evaluated_at DATETIME NULL",
                    )
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
