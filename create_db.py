"""Create the Band Inventory SQLite database.

Usage:
    python create_db.py            # empty database (schema only)
    python create_db.py --sample   # schema + sample data (database.sql)
    python create_db.py --reset    # delete and rebuild the database first
"""
import argparse
import sqlite3
from pathlib import Path

HERE = Path(__file__).parent
DB_PATH = HERE / "band_inventory.db"
SCHEMA = HERE / "schema.sql"
SAMPLE = HERE / "database.sql"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", action="store_true", help="load sample data")
    parser.add_argument("--reset", action="store_true", help="delete the existing database first")
    args = parser.parse_args()

    if args.reset and DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA.read_text())
        if args.sample:
            conn.executescript(SAMPLE.read_text())

    print(f"Database ready: {DB_PATH}")


if __name__ == "__main__":
    main()
