"""
Compatibility shim for legacy backend startup commands.

This module re-exports the real FastAPI application from `backend.app.main`
so older commands like `python -m uvicorn app.main:app --reload` keep working.
"""

from backend.app.main import app

