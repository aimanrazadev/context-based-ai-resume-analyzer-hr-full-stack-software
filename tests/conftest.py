import os
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


# Ensure `import backend.app...` works regardless of where pytest is run from.
BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def test_db_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("db") / "test.sqlite3"


@pytest.fixture()
def app(test_db_path: Path) -> FastAPI:
    """
    Create a FastAPI app wired to a temporary SQLite DB.

    We intentionally do NOT import `app.main` to avoid MySQL-only startup migrations.
    """
    # Must be set before importing app.database so engine init doesn't choke on empty DATABASE_URL.
    os.environ["DISABLE_DOTENV"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{test_db_path}"
    os.environ["UPLOAD_DIR"] = str(test_db_path.parent / "uploads")
    # Ensure tests never call external AI providers even if developer machine has keys set.
    os.environ["GEMINI_API_KEY"] = ""
    os.environ["AI_API_KEY"] = ""
    # Prevent local embedding model downloads during tests; we monkeypatch semantic scoring when needed.
    os.environ["EMBEDDINGS_ENABLED"] = "0"

    from backend.app import database as db

    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Patch the shared database module so router dependencies use the test DB.
    db.engine = engine
    db.SessionLocal = TestingSessionLocal

    # Import models so Base metadata is populated, then create tables.
    from backend.app import models  # noqa: F401

    db.Base.metadata.drop_all(bind=engine)
    db.Base.metadata.create_all(bind=engine)

    from backend.app.api import auth as auth_api
    from backend.app.api import interview as interview_api
    from backend.app.api import job as job_api
    from backend.app.api import resume as resume_api

    fastapi_app = FastAPI()
    fastapi_app.include_router(auth_api.router)
    fastapi_app.include_router(job_api.router)
    fastapi_app.include_router(resume_api.router)
    fastapi_app.include_router(interview_api.router)

    return fastapi_app


@pytest.fixture()
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


@pytest.fixture()
def db_session(app: FastAPI):
    """
    Direct SQLAlchemy session bound to the same temporary SQLite DB used by the test app.
    """
    from backend.app.database import SessionLocal

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

