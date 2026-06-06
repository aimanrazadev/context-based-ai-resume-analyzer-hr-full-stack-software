"""
One-time helper to download and validate the local cross-encoder reranker cache.

Run:
    .\.venv\Scripts\python.exe scripts\warm_reranker.py
"""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.services.reranking import warm_reranker_cache


def main() -> None:
    path = warm_reranker_cache(force_download=True)
    print(f"Reranker ready: {path}")


if __name__ == "__main__":
    main()
