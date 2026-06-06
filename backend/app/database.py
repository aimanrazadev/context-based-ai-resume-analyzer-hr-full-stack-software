import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    # Allow simpler `.env` values like `mysql://...` and upgrade to the driver form.
    return url.replace("mysql://", "mysql+pymysql://", 1) if url.startswith("mysql://") else url


def _require_mysql_database_url(url: str) -> str:
    """
    Normalize and validate the configured database URL for a MySQL-only backend.

    Args:
        url: Raw DATABASE_URL from configuration.

    Returns:
        A SQLAlchemy-compatible MySQL URL.

    Side Effects:
        None.

    Error Handling:
        Raises ValueError when DATABASE_URL is missing or points to a
        non-MySQL database.
    """
    normalized = _normalize_database_url((url or "").strip())
    if not normalized:
        raise ValueError(
            "DATABASE_URL is required and must point to MySQL, for example "
            "'mysql+pymysql://user:password@localhost:3306/ai_resume_analyzer'."
        )
    if normalized.startswith("sqlite"):
        raise ValueError("SQLite is no longer supported. Configure a MySQL DATABASE_URL.")
    if not normalized.startswith("mysql+pymysql://"):
        raise ValueError("Only MySQL databases are supported in this backend.")
    return normalized


_db_url = _require_mysql_database_url(DATABASE_URL)
_engine_kwargs = {"pool_pre_ping": True}

engine = create_engine(_db_url, **_engine_kwargs)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    # Import models so they register with SQLAlchemy metadata before create_all.
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
