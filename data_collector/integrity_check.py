"""
Daily integrity check for the offers table.

Three audits, run after collect.py each day:

  1. NULL audit on columns the modeling pipeline depends on
     (price, airline, departure_at, return_at, trip_duration_days,
      lead_time_days) — any NULL here breaks training.

  2. Range audit — flags impossible values (negative price, zero
     price, negative lead time, etc.) that would indicate upstream
     corruption or a collector bug.

  3. Volume audit — flags days where offer count drops >25% below
     the 3-day rolling baseline, indicating possible API issues.

Exits with status 1 if anything is flagged, so launchd's stderr log
captures the alert. Exit 0 means the new batch is clean and safe to
train against.
"""
import argparse
import sqlite3
import sys


NULL_COLUMNS = [
    "price",
    "airline",
    "departure_at",
    "return_at",
    "trip_duration_days",
    "lead_time_days",
]

RANGE_CHECKS = {
    "price <= 0":          "SELECT COUNT(*) FROM offers WHERE price <= 0",
    "price > 50000":       "SELECT COUNT(*) FROM offers WHERE price > 50000",
    "lead_time < 0":       "SELECT COUNT(*) FROM offers WHERE lead_time_days < 0",
    "trip_duration < 0":   "SELECT COUNT(*) FROM offers WHERE trip_duration_days < 0",
    "trip_duration > 365": "SELECT COUNT(*) FROM offers WHERE trip_duration_days > 365",
}

VOLUME_DROP_THRESHOLD = 0.75  # flag if latest day < 75% of 3-day rolling avg


def null_audit(cur):
    out = {}
    for col in NULL_COLUMNS:
        cur.execute(f"SELECT COUNT(*) FROM offers WHERE {col} IS NULL")
        out[col] = cur.fetchone()[0]
    return out


def range_audit(cur):
    return {name: cur.execute(q).fetchone()[0] for name, q in RANGE_CHECKS.items()}


def recent_volumes(cur, days=10):
    cur.execute("""
        SELECT DATE(captured_at) AS day, COUNT(*) AS n
        FROM offers
        GROUP BY DATE(captured_at)
        ORDER BY day DESC
        LIMIT ?
    """, (days,))
    return cur.fetchall()


def main(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    nulls = null_audit(cur)
    ranges = range_audit(cur)
    volumes = recent_volumes(cur)

    flags = []

    print("=== NULL audit ===")
    for col, n in nulls.items():
        marker = "  [FLAG]" if n > 0 else ""
        print(f"  {col:24s} {n}{marker}")
        if n > 0:
            flags.append(f"NULL in {col}: {n}")

    print("\n=== Range audit ===")
    for name, n in ranges.items():
        marker = "  [FLAG]" if n > 0 else ""
        print(f"  {name:24s} {n}{marker}")
        if n > 0:
            flags.append(f"Range violation {name}: {n}")

    print("\n=== Volume (last 10 capture days) ===")
    for day, n in volumes:
        print(f"  {day}  {n}")

    if len(volumes) >= 4:
        latest = volumes[0][1]
        baseline = sum(r[1] for r in volumes[1:4]) / 3
        if latest < baseline * VOLUME_DROP_THRESHOLD:
            msg = f"latest ({latest}) is {(1 - latest/baseline)*100:.0f}% below 3-day baseline ({baseline:.0f})"
            print(f"\n  [FLAG] {msg}")
            flags.append(f"Volume drop: {msg}")

    conn.close()

    if flags:
        print(f"\n{len(flags)} anomaly(ies) flagged.")
        return 1

    print("\nAll integrity checks passed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily integrity check for the offers table.")
    parser.add_argument("--db", default="data/flights.db")
    args = parser.parse_args()
    sys.exit(main(args.db))
