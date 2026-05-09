"""
Daily flight data collector. Fetches offers from the flight pricing API
and inserts each returned offer as a row into data/flights.db.
"""
import os
import json
import sqlite3
from pathlib import Path

import requests
from dotenv import load_dotenv

from datetime import datetime, timezone



# Load API config from .env
load_dotenv(Path(__file__).parent / ".env")
token = os.environ["API_TOKEN"]

ROUTES = [ #will implement popular routes (another API) in the future and store it in separate db
    ("JFK", "LHR"),
    ("JFK", "CDG"),
    ("YYZ", "LHR"),
]

connection = sqlite3.connect("data/flights.db")

cur = connection.cursor()
captured_at = datetime.now(timezone.utc).isoformat()

for origin, destination in ROUTES:

    # Define the endpoint URL and the query parameters
    URL = os.environ["API_URL"] #-> May move outside loop
    params = {
        "origin": origin,
        "destination": destination,
        "departure_at": "2026-08",
        "currency": "usd",
        "market": "us",
        "one_way": "true",
        "limit": 1000,
        "token": token,
    }


    # Send the GET request and pull out the offers list
    response = requests.get(URL, params=params)
    offers = response.json().get("data", [])

    print(f"Status: {response.status_code}")
    print(f"Fetched {len(offers)} offers")

    for offer in offers:
        cur.execute(
            """
            INSERT INTO offers (
                captured_at, lead_time_days,
                origin, destination, origin_airport, destination_airport,
                airline, flight_number, departure_at,
                transfers, return_transfers,
                duration, duration_to, duration_back,
                class, price, currency, gate, link, raw_offer
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                captured_at,
                None,                              # lead_time_days
                offer["origin"],
                offer["destination"],
                offer.get("origin_airport"),
                offer.get("destination_airport"),
                offer.get("airline"),
                offer.get("flight_number"),
                offer["departure_at"],
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


connection.commit()
connection.close()
