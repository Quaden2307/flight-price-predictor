"""
One-time loader: filter the public airports CSV down to the IATA codes used in
ROUTES, PLUS a supplemental set of codes the pricing API returns that ROUTES
never asks for, and insert them into the airports table in flights.db.

Why the supplement (see documentation/modeling_runs.md run #3):
The collector *queries* airport codes (JFK, LHR, ...), but the API often *labels*
offers with metropolitan/city codes (NYC, TYO, LON, ...) or with airports we
never routed through. Those codes never entered the airports table, so
build_features() couldn't find coordinates and its dropna() silently deleted
~91% of all offers. Covering them recovers the data (~8k -> ~98k training rows).

  - EXTRA_AIRPORT_CODES: real airports present in the CSV but absent from ROUTES.
    Just added to the load set so the CSV loop picks up their real coordinates.
  - CITY_CODES: metropolitan codes with NO airport-level CSV row. Mapped to their
    primary international airport's coordinates. distance_km is a coarse
    great-circle feature, so the city-centroid approximation is harmless.
"""
import csv
import sqlite3
from pathlib import Path

from routes import ROUTES

#Cleaner paths (safer)
ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "flights.db"
CSV_PATH = ROOT / "data" / "airports.csv"

# Real airports the API returns but ROUTES never queried. Already in the CSV,
# so we only need to add them to the load set and let the CSV loop do the rest.
EXTRA_AIRPORT_CODES = {"SHA", "ORL", "HOU", "ONT", "OAK", "LGB", "PAE"}

# Metropolitan codes with no airport-level CSV row.
# iata -> (name, city, country, latitude, longitude); coords = city's primary airport.
CITY_CODES = {
    "NYC": ("New York (all airports)",   "New York",   "US",  40.6413,  -73.7781),  # JFK
    "TYO": ("Tokyo (all airports)",      "Tokyo",      "JP",  35.5494,  139.7798),  # HND
    "SEL": ("Seoul (all airports)",      "Seoul",      "KR",  37.4602,  126.4407),  # ICN
    "CHI": ("Chicago (all airports)",    "Chicago",    "US",  41.9742,  -87.9073),  # ORD
    "LON": ("London (all airports)",     "London",     "GB",  51.4700,   -0.4543),  # LHR
    "PAR": ("Paris (all airports)",      "Paris",      "FR",  49.0097,    2.5479),  # CDG
    "BJS": ("Beijing (all airports)",    "Beijing",    "CN",  40.0799,  116.6031),  # PEK
    "ROM": ("Rome (all airports)",       "Rome",       "IT",  41.8003,   12.2389),  # FCO
    "SAO": ("Sao Paulo (all airports)",  "Sao Paulo",  "BR", -23.4356,  -46.4731),  # GRU
    "WAS": ("Washington (all airports)", "Washington", "US",  38.9531,  -77.4565),  # IAD
    "YTO": ("Toronto (all airports)",    "Toronto",    "CA",  43.6777,  -79.6248),  # YYZ
    "YMQ": ("Montreal (all airports)",   "Montreal",   "CA",  45.4706,  -73.7408),  # YUL
    "YEA": ("Edmonton (all airports)",   "Edmonton",   "CA",  53.3097, -113.5801),  # YEG
    "DTT": ("Detroit (all airports)",    "Detroit",    "US",  42.2124,  -83.3534),  # DTW
}

airport_set = set(EXTRA_AIRPORT_CODES)
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

# Metropolitan codes aren't in the CSV, so insert them from the table above.
# Tagged airport_type='metro' so they stay distinguishable from real airports.
for iata, (name, city, country, lat, lon) in CITY_CODES.items():
    cur.execute(
        """
        INSERT OR REPLACE INTO airports (
            iata, name, city, country, latitude, longitude, hub_tier, airport_type
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (iata, name, city, country, lat, lon, None, "metro"),
    )


connection.commit()   # save changes
connection.close()    # clean up
