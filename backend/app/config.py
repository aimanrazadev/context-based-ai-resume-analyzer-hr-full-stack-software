import os
from pathlib import Path
from dotenv import load_dotenv

# Override=True so changes in backend/.env take effect on process reload (and not get
# stuck on old environment variables).
#
# Set DISABLE_DOTENV=1 when a caller provides its own MySQL environment.
if os.getenv("DISABLE_DOTENV") != "1":
    load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

_raw_database_url = (os.getenv("DATABASE_URL") or "").strip()
DATABASE_URL = _raw_database_url

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-2.0-flash-lite,gemini-2.0-flash-lite-001,gemini-flash-lite-latest").split(",")
    if model.strip()
]
GEMINI_BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
GEMINI_API_VERSION = os.getenv("GEMINI_API_VERSION", "v1")

# Keep defaults tight so the UI doesn't hit its request timeout on transient AI failures.
# You can still override via backend/.env for longer runs.
AI_TIMEOUT_S = float(os.getenv("AI_TIMEOUT_S", "10") or "10")
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "1") or "1")
AI_LOG_PAYLOADS = (os.getenv("AI_LOG_PAYLOADS", "0") or "0").strip() in {"1", "true", "True", "yes", "YES"}

# File uploads
# Absolute path; override with UPLOAD_DIR in env (useful for tests).
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or (Path(__file__).resolve().parent.parent / "uploads").as_posix()

# Auth / JWT
# NOTE: keep a default for local dev so the server can boot even if SECRET_KEY isn't set.
SECRET_KEY = os.getenv("SECRET_KEY", "dev_secret_change_me")

# -------------------- Module 9: Embeddings (local) --------------------
EMBEDDINGS_ENABLED = (os.getenv("EMBEDDINGS_ENABLED", "1") or "1").strip() in {"1", "true", "True", "yes", "YES"}
EMBEDDINGS_PROVIDER = os.getenv("EMBEDDINGS_PROVIDER", "local")
EMBEDDINGS_MODEL = os.getenv("EMBEDDINGS_MODEL", "BAAI/bge-small-en-v1.5")

