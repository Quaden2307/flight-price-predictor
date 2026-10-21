"""
Standalone airport-coverage check against the live database.

Every origin/destination code in `offers` must exist in `airports`; otherwise
build_features() loses those rows to dropna without an error (the June 2026
92%-row-drop bug). Run this after ANY route change, and again after the first
collection that follows it, because the API may label a new route with a metro
code you have never seen (EZE -> BUE, Bangkok, ...).

    venv/bin/python -m src.check_coverage              # whole offers table
    venv/bin/python -m src.check_coverage --snapshot   # only rows captured <= SNAPSHOT_DATE

Exit 1 on any missing code, same convention as data_collector/audit.py, so it
can sit in the route-change smoke test next to the other checks.
"""
import argparse
import sqlite3
import sys

import pandas as pd

from src.config import SNAPSHOT_DATE
from src.guards import GuardError, check_airport_coverage

DB_PATH = "data/flights.db"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--snapshot", action="store_true",
                        help=f"restrict to offers captured on or before SNAPSHOT_DATE ({SNAPSHOT_DATE})")
    args = parser.parse_args()

    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        query = "SELECT origin, destination FROM offers"
        if args.snapshot:
            query += f" WHERE date(captured_at) <= '{SNAPSHOT_DATE}'"
        offers = pd.read_sql(query, conn)
        airports = pd.read_sql("SELECT iata FROM airports", conn)
    finally:
        conn.close()

    label = f"offers <= {SNAPSHOT_DATE}" if args.snapshot else "all offers"
    print(f"{len(offers)} rows, {len(airports)} airport rows ({label})")
    try:
        check_airport_coverage(offers, airports, label=label)
    except GuardError as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
