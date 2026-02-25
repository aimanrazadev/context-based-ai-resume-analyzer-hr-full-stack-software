"""Repo-root Uvicorn entrypoint.

Allows running the backend from the repo root:

    uvicorn app.main:app --reload

This simply re-exports the FastAPI app defined in `backend/app/main.py`.
"""

from backend.app.main import app  # re-export

