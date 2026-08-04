"""
One-time database initialisation script.

Creates all tables defined in models.py if they do not already exist.
Safe to re-run (uses CREATE TABLE IF NOT EXISTS under the hood).

Usage:
    python scripts/init_db.py

Run this once before the first deployment, or after adding new models.
This will eventually be replaced by Alembic migrations.
"""

import sys
import os

# Allow running from the project root or from the scripts/ directory
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from database import engine, Base
import models  # registers GithubEvent, AuditLog on Base.metadata


def init_db():
    print("Creating database tables...")
    Base.metadata.create_all(bind=engine)
    print("Done. Tables created (or already exist):")
    for table_name in Base.metadata.tables:
        print(f"  - {table_name}")


if __name__ == "__main__":
    init_db()
