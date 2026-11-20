"""Copy everything from the local SQLite database into a hosted Postgres database (e.g. Neon), so the
deployed app shows the same companies, sources, crawl history, signals and briefs as the local run.

Usage (from backend/):
    set TARGET_DATABASE_URL=postgresql://...      (Windows)   |   export TARGET_DATABASE_URL=postgresql://...
    python scripts/copy_to_postgres.py

The target must be empty (fresh tables are created). The connection string is read from the environment
only and never printed.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine, func, select, text  # noqa: E402

from app.db import Base  # noqa: E402
from app import models  # noqa: E402,F401  (registers tables)


def normalise(url: str) -> str:
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


def main():
    target_url = os.getenv("TARGET_DATABASE_URL", "").strip()
    if not target_url:
        sys.exit("Set TARGET_DATABASE_URL to the Postgres connection string first.")
    source = create_engine(f"sqlite:///{Path(__file__).resolve().parent.parent / 'signalstack.db'}")
    target = create_engine(normalise(target_url))
    Base.metadata.create_all(target)

    with target.connect() as t:
        if t.execute(select(func.count()).select_from(models.Company.__table__)).scalar():
            sys.exit("Target already contains companies; refusing to overwrite. Use an empty database.")

    tables = Base.metadata.sorted_tables  # parents before children (foreign keys)
    with source.connect() as s, target.begin() as t:
        for table in tables:
            rows = [dict(r._mapping) for r in s.execute(select(table))]
            if rows:
                for i in range(0, len(rows), 500):
                    t.execute(table.insert(), rows[i:i + 500])
            print(f"{table.name:18s} {len(rows):6d} rows")
        # keep Postgres id sequences ahead of the copied ids
        for table in tables:
            if "id" in table.c:
                t.execute(text(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 0) + 1, false)"))
    print("Done.")


if __name__ == "__main__":
    main()
