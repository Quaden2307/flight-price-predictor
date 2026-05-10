"""
Daily collector. Calls the flight pricing API and writes offers to data/flights.db.
"""
import os
import json
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv

from datetime import datetime, timezone

from routes import ROUTES


# Load API config from .env
load_dotenv(Path(__file__).parent / ".env")
token = os.environ["API_TOKEN"]

connection = sqlite3.connect("data/flights.db")

cur = connection.cursor()
captured_at = datetime.now(timezone.utc).isoformat()
today = datetime.now(timezone.utc).date()

'''
captured_at and today represent the same moment in time, however in different formats:
captured_at is stored as a string in the database, whereas today is used for math. (Not added to db)
'''

# Current month + 6 months ahead. Querying by month returns more offers per call than by date.
DEPART_MONTHS = []
year, month_num = today.year, today.month
for _ in range(7):
    DEPART_MONTHS.append(f"{year:04d}-{month_num:02d}")
    month_num += 1
    if month_num > 12:
        month_num = 1
        year += 1


def offset_month(month_str, offset):
    # Shift YYYY-MM forward by N months
    y, m = map(int, month_str.split("-"))
    m += offset
    while m > 12:
        m -= 12
        y += 1
    return f"{y:04d}-{m:02d}"


'''
Round-trip duration offsets — months between depart and return month.
The API caps round-trip queries at a 30-day gap, so we can only do offset 0
(same month, 1-30d trips) and offset 1 (next month, up to ~60d). Anything
longer (semester-long, internships) needs a different API and is on hold.
'''
DURATION_OFFSETS = [0, 1]


'''
Business and first class data will be collected in a separate script and in
higher intervals than economy API calls. Most users will be searching for economy
anyway, but business may be useful since routes lean toward tech-industry travel
which has more corporate booking.
'''
CLASSES = [0, 1, 2]  # 0=economy, 1=business, 2=first -> SEPARATE SCRIPT


URL = os.environ["API_URL"]

# Run-level counters
api_calls = 0
offers_inserted = 0
failures = 0

for origin, destination in ROUTES:
    for depart_month in DEPART_MONTHS:
        for offset in DURATION_OFFSETS:
            return_month = offset_month(depart_month, offset)

            params = {
                "origin": origin,
                "destination": destination,
                "departure_at": depart_month,
                "return_at": return_month,
                "currency": "usd",
                "market": "us",
                "one_way": "false",
                "limit": 1000,
                "token": token,
            }

            api_calls += 1
            try:
                response = requests.get(URL, params=params, timeout=10)
                response.raise_for_status()
                offers = response.json().get("data", [])
            except Exception as e:
                print(f"{origin}→{destination} ({depart_month}→{return_month}): FAILED — {e}")
                failures += 1
                continue

            print(f"{origin}→{destination} ({depart_month}→{return_month}): {len(offers)} offers")

            for offer in offers:
                # Lead time and trip duration come from the offer's actual dates, not the query month.
                depart_date = datetime.fromisoformat(offer["departure_at"]).date()
                lead = (depart_date - today).days
                if lead < 0:
                    continue

                return_at = offer.get("return_at")
                trip_duration_days = None
                if return_at:
                    return_date = datetime.fromisoformat(return_at).date()
                    trip_duration_days = (return_date - depart_date).days

                cur.execute(
                    """
                    INSERT INTO offers (
                        captured_at, lead_time_days,
                        origin, destination, origin_airport, destination_airport,
                        airline, flight_number, departure_at, return_at, trip_duration_days,
                        transfers, return_transfers,
                        duration, duration_to, duration_back,
                        flight_class, price, currency, gate, link, raw_offer
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        captured_at,
                        lead,
                        offer["origin"],
                        offer["destination"],
                        offer.get("origin_airport"),
                        offer.get("destination_airport"),
                        offer.get("airline"),
                        offer.get("flight_number"),
                        offer["departure_at"],
                        return_at,
                        trip_duration_days,
                        offer.get("transfers"),
                        offer.get("return_transfers"),
                        offer.get("duration"),
                        offer.get("duration_to"),
                        offer.get("duration_back"),
                        0,
                        offer["price"],
                        "usd",
                        offer.get("gate"),
                        offer.get("link"),
                        json.dumps(offer),
                    ),
                )
                offers_inserted += 1


# Log this run
finished_at = datetime.now(timezone.utc).isoformat()
cur.execute(
    "INSERT INTO runs_logs (started_at, finished_at, api_calls, offers_inserted, failures) VALUES (?, ?, ?, ?, ?)",
    (captured_at, finished_at, api_calls, offers_inserted, failures),
)
print(f"\nDone: {api_calls} API calls, {offers_inserted} offers inserted, {failures} failures")

connection.commit()
connection.close()
