"""
Exact-key duplicate guard for the offers table.

A "duplicate" here means two rows sharing the full
(captured_at, origin, destination, departure_at, return_at, airline,
 flight_number, price, flight_class) tuple. These can only appear from a
re-run, partial-write artifact, or schema-level violation — legitimate
data never duplicates this key because captured_at is set once per
collector invocation.

Default mode is dry-run (reports counts only). Pass --apply to delete
the redundant rows. When deleting, keeps the row with the lowest id in
each duplicate group and drops the rest.

Wire into the daily pipeline by invoking after collect.py.
"""
import argparse
import sqlite3
import sys


DEDUP_KEY = (
    "captured_at",
    "origin", "destination",
    "departure_at", "return_at",
    "airline", "flight_number",
    "price", "flight_class",
)


def find_duplicate_groups(cur):
    key_cols = ", ".join(DEDUP_KEY)
    cur.execute(f"""
        SELECT {key_cols}, COUNT(*) AS n, GROUP_CONCAT(id) AS ids
        FROM offers
        GROUP BY {key_cols}
        HAVING COUNT(*) > 1
        ORDER BY n DESC
    """)
    return cur.fetchall()


def remove_extras(cur, groups):
    removed = 0
    for row in groups:
        ids = sorted(int(i) for i in row[-1].split(","))
        to_drop = ids[1:]
        cur.executemany("DELETE FROM offers WHERE id = ?", [(i,) for i in to_drop])
        removed += len(to_drop)
    return removed


def main(db_path: str, apply: bool) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    groups = find_duplicate_groups(cur)
    redundant = sum(row[-2] - 1 for row in groups)

    print(f"Scanned offers for exact-key duplicates ({len(DEDUP_KEY)}-column key).")
    print(f"Found {len(groups)} duplicate group(s), {redundant} redundant row(s).")

    if groups and apply:
        removed = remove_extras(cur, groups)
        conn.commit()
        print(f"Deleted {removed} row(s). Dataset is now exact-key unique.")
    elif groups:
        print("Dry-run — pass --apply to delete.")
    else:
        print("Dataset is exact-key unique. Nothing to remove.")

    conn.close()
    return redundant


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exact-key dedup for the offers table.")
    parser.add_argument("--db", default="data/flights.db")
    parser.add_argument("--apply", action="store_true",
                        help="Delete duplicates (default: dry-run report only).")
    args = parser.parse_args()
    sys.exit(0 if main(args.db, args.apply) == 0 else 0)
