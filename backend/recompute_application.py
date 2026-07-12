import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.api.job import _analyze_and_update_existing_application
from backend.app.database import SessionLocal


async def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate AI analysis and scoring for one application.")
    parser.add_argument("application_id", type=int)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        await _analyze_and_update_existing_application(db=db, application_id=args.application_id)
        print(f"Recomputed application {args.application_id}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
