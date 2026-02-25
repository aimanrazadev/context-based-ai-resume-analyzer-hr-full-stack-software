"""Root-level app shim.

This package exists so `uvicorn app.main:app` works when launched from the repo root.
The real FastAPI application lives in `backend/app/main.py`.
"""

