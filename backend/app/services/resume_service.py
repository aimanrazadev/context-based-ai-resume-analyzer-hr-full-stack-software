"""Canonical resume extraction service surface."""

from .resume_analysis import extract_and_clean_resume_text

__all__ = ["extract_and_clean_resume_text"]
