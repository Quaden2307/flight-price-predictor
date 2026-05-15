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


connection = sqlite3.connect("data/flights.db")
cur = connection.cursor()

with open("data/airports.csv", newline="") as f:
    airports = csv.DictReader(f)
    for airport in airports:



connection.commit()   # save changes
connection.close()    # clean up
