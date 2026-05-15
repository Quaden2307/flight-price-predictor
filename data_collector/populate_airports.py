"""
One-time loader: filter the public airports CSV down to the IATA codes (JFK, YYZ, YVR)
used in ROUTES, and insert them into the airports table in flights.db.
"""
import csv
import sqlite3
from pathlib import Path

from routes import ROUTES

#Cleaner paths (safer)
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "flights.db"
CSV_PATH = ROOT / "data" / "airports.csv"

airport_set = set()
for origin, destination in ROUTES:
    airport_set.add(origin)
    airport_set.add(destination)


connection = sqlite3.connect(DB_PATH)
cur = connection.cursor()

# Add airport_type if it doesn't exist yet. SQLite has no "ADD COLUMN IF NOT EXISTS",
# so catch the duplicate-column error on re-runs.
try:
    cur.execute("ALTER TABLE airports ADD COLUMN airport_type TEXT")
except sqlite3.OperationalError:
    pass

with open(CSV_PATH, newline="") as f:
    airports = csv.DictReader(f)
    for airport in airports:
        if airport["iata_code"] in airport_set:
            cur.execute(
                """
                INSERT OR REPLACE INTO airports (
                    iata, name, city, country, latitude, longitude, hub_tier, airport_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    airport["iata_code"],
                    airport["name"],
                    airport["municipality"],
                    airport["iso_country"],
                    float(airport["latitude_deg"]),
                    float(airport["longitude_deg"]),
                    None,
                    airport["type"],
                ),
            )



        


connection.commit()   # save changes
connection.close()    # clean up
