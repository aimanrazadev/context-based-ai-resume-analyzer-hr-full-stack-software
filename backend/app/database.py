import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import DATABASE_URL

logger = logging.getLogger(__name__)


def _normalize_database_url(url: str) -> str:
    # Allow simpler `.env` values like `mysql://...` and upgrade to the driver form.
    return url.replace("mysql://", "mysql+pymysql://", 1) if url.startswith("mysql://") else url


_db_url = _normalize_database_url((DATABASE_URL or "").strip())
_engine_kwargs = {"pool_pre_ping": True}
if _db_url.startswith("sqlite"):
    # Needed for SQLite when used with FastAPI/uvicorn (multiple threads).
    # Also set a busy timeout to reduce "database is locked" errors under concurrent requests.
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}

engine = create_engine(_db_url, **_engine_kwargs)

if _db_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record):  # noqa: ANN001
        try:
            cursor = dbapi_connection.cursor()
            # Better concurrency for reads+writes in local dev.
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.close()
        except Exception as e:
            logger.warning("Failed to set SQLite pragmas: %s", e)

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
