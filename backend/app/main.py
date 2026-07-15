import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from .api import auth as auth_api
from .api import job as job_api
from .api import recruiter as recruiter_api
from .database import create_database_tables, engine
from .utils.error_handlers import get_error_message
from .services.application_service import backfill_missing_application_scores

app = FastAPI(title="HireEZ")

app.include_router(auth_api.router)
app.include_router(job_api.router)
app.include_router(recruiter_api.router)

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


_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173", "https://context-based-ai-resume-analyzer-hr.vercel.app"]
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
        dialect = (getattr(engine, "dialect", None) and engine.dialect.name) or ""
        dialect = str(dialect).lower()
        if dialect == "sqlite":
            raise RuntimeError("SQLite is no longer supported. Configure a MySQL DATABASE_URL.")
        if dialect and dialect != "mysql":
            raise RuntimeError(f"Unsupported database dialect '{dialect}'. This backend now requires MySQL.")

        create_database_tables()

        from .database import SessionLocal
        with SessionLocal() as db:
            backfill_missing_application_scores(db)

        app.state.db_init_error = None
    except Exception as e:
        logger.exception("Database initialization failed")
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
