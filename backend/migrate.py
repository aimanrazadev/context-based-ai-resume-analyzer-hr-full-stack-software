#!/usr/bin/env python3
"""
Migration script to add AIMatchCache table.
Run this after updating the models to ensure the table is created.
"""

import sys
from pathlib import Path

from sqlalchemy import inspect, text

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from app.database import init_db, Base, engine

def migrate():
    print("Initializing database with all models...")
    init_db()
    print("✓ Database initialized successfully")

    inspector = inspect(engine)
    existing = {c["name"] for c in inspector.get_columns("jobs")}
    dialect = engine.dialect.name

    columns_to_add = {
        "short_description": "VARCHAR(255)",
        "opportunity_type": "VARCHAR(20)",
        "min_experience_years": "INTEGER",
        "job_type": "VARCHAR(20)",
        "job_site": "VARCHAR(20)",
        "openings": "INTEGER",
        "salary_currency": "VARCHAR(5)",
        "salary_min": "INTEGER",
        "salary_max": "INTEGER",
        "variable_min": "INTEGER",
        "variable_max": "INTEGER",
        "perks": "TEXT",
        "additional_preferences": "TEXT",
        "non_negotiables": "TEXT",
        "screening_availability": "VARCHAR(255)",
        "screening_phone": "VARCHAR(30)",
        "start_date": "TIMESTAMP",
        "duration": "VARCHAR(100)",
        "apply_by": "TIMESTAMP",
    }

    added = []
    for col, col_type in columns_to_add.items():
        if col in existing:
            continue
        ddl = f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"
        if dialect == "sqlite":
            ddl = f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"  # SQLite supports ADD COLUMN
        try:
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(col)
        except Exception as e:
            print(f"✗ Failed to add column {col}: {e}")

    if added:
        print(f"✓ Added job columns: {', '.join(added)}")
    else:
        print("✓ Job columns already up to date")

    # Enforce one application per (candidate_id, job_id) when possible.
    # If duplicates already exist, creation may fail; API-level checks still prevent new duplicates.
    try:
        uniq_name = "uq_applications_candidate_job"
        existing_index_names = {i.get("name") for i in inspector.get_indexes("applications") if i.get("name")}
        existing_unique_names = {
            u.get("name") for u in inspector.get_unique_constraints("applications") if u.get("name")
        }
        if uniq_name not in existing_index_names and uniq_name not in existing_unique_names:
            with engine.begin() as conn:
                conn.execute(text(
                    "CREATE UNIQUE INDEX uq_applications_candidate_job ON applications (candidate_id, job_id)"
                ))
            print("✓ Added unique index: uq_applications_candidate_job")
        else:
            print("✓ Unique index already exists: uq_applications_candidate_job")
    except Exception as e:
        print(f"⚠ Could not add unique index uq_applications_candidate_job: {e}")
    
    # Verify AIMatchCache table exists
    from app.models import AIMatchCache  # noqa: F401
    if "ai_match_cache" in Base.metadata.tables:
        print("✓ AIMatchCache table created")
    else:
        print("✗ AIMatchCache table not found")
        return False
    
    return True

if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
