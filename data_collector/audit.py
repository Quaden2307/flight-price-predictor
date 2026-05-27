"""
Daily audit of the offers table.

Three checks, run after collect.py each day:

  1. NULLs — any NULL in price, airline, departure_at, return_at,
     trip_duration_days, or lead_time_days breaks training.

  2. Ranges — impossible values (negative price, zero price,
     negative lead time, etc.) that point to upstream corruption
     or a collector bug.

  3. Volume — two ways:
       a) Relative: today < 75% of the 3-day rolling avg. Catches
          sudden cliffs.
       b) Absolute: last N days all below a hard floor. Catches
          gradual erosion the relative check misses once the
          baseline slides down with it.

Exits 1 if anything is flagged so launchd's stderr log captures
it. Exit 0 means the new batch is clean.
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
ABSOLUTE_VOLUME_FLOOR = 3000      # hard floor, independent of recent baseline
ABSOLUTE_FLOOR_CONSECUTIVE = 2    # only fire after N days in a row below the floor


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

    if len(volumes) >= ABSOLUTE_FLOOR_CONSECUTIVE:
        recent = volumes[:ABSOLUTE_FLOOR_CONSECUTIVE]
        if all(n < ABSOLUTE_VOLUME_FLOOR for _, n in recent):
            counts = ", ".join(str(n) for _, n in recent)
            msg = f"{ABSOLUTE_FLOOR_CONSECUTIVE} consecutive days < {ABSOLUTE_VOLUME_FLOOR} ({counts})"
            print(f"  [FLAG] Absolute floor: {msg}")
            flags.append(f"Absolute floor: {msg}")

    conn.close()

    if flags:
        print(f"\n{len(flags)} anomaly(ies) flagged.")
        return 1

    print("\nAll audits passed.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Daily audit of the offers table.")
    parser.add_argument("--db", default="data/flights.db")
    args = parser.parse_args()
    sys.exit(main(args.db))
