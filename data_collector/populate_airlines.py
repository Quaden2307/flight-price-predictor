"""
One-time loader: insert hand-curated airline classifications into the airlines
table in flights.db. Covers the top ~25 carriers by row count in offers.
Re-runnable via INSERT OR REPLACE.
"""
import sqlite3
from pathlib import Path


ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / "data" / "flights.db"


AIRLINES = {
    "F9": {"name": "Frontier Airlines",        "country": "US", "type": "lcc",    "alliance": None},
    "AA": {"name": "American Airlines",        "country": "US", "type": "legacy", "alliance": "oneworld"},
    "B6": {"name": "JetBlue Airways",          "country": "US", "type": "hybrid", "alliance": None},
    "UA": {"name": "United Airlines",          "country": "US", "type": "legacy", "alliance": "star"},
    "AC": {"name": "Air Canada",               "country": "CA", "type": "legacy", "alliance": "star"},
    "WS": {"name": "WestJet",                  "country": "CA", "type": "hybrid", "alliance": None},
    "AS": {"name": "Alaska Airlines",          "country": "US", "type": "legacy", "alliance": "oneworld"},
    "FI": {"name": "Icelandair",               "country": "IS", "type": "hybrid", "alliance": None},
    "SC": {"name": "Shandong Airlines",        "country": "CN", "type": "legacy", "alliance": None},
    "PD": {"name": "Porter Airlines",          "country": "CA", "type": "hybrid", "alliance": None},
    "CX": {"name": "Cathay Pacific",           "country": "HK", "type": "legacy", "alliance": "oneworld"},
    "OZ": {"name": "Asiana Airlines",          "country": "KR", "type": "legacy", "alliance": "star"},
    "F8": {"name": "Flair Airlines",           "country": "CA", "type": "lcc",    "alliance": None},
    "MM": {"name": "Peach Aviation",           "country": "JP", "type": "lcc",    "alliance": None},
    "DE": {"name": "Condor",                   "country": "DE", "type": "hybrid", "alliance": None},
    "ZG": {"name": "ZIPAIR Tokyo",             "country": "JP", "type": "lcc",    "alliance": None},
    "UO": {"name": "HK Express",               "country": "HK", "type": "lcc",    "alliance": None},
    "WN": {"name": "Southwest Airlines",       "country": "US", "type": "lcc",    "alliance": None},
    "QR": {"name": "Qatar Airways",            "country": "QA", "type": "legacy", "alliance": "oneworld"},
    "MU": {"name": "China Eastern Airlines",   "country": "CN", "type": "legacy", "alliance": "skyteam"},
    "EI": {"name": "Aer Lingus",               "country": "IE", "type": "hybrid", "alliance": None},
    "KE": {"name": "Korean Air",               "country": "KR", "type": "legacy", "alliance": "skyteam"},
    "TS": {"name": "Air Transat",              "country": "CA", "type": "hybrid", "alliance": None},
    "Y4": {"name": "Volaris",                  "country": "MX", "type": "lcc",    "alliance": None},
    "IJ": {"name": "Spring Japan",             "country": "JP", "type": "lcc",    "alliance": None},
}


connection = sqlite3.connect(DB_PATH)
cur = connection.cursor()

for iata, info in AIRLINES.items():
    cur.execute(
        """
        INSERT OR REPLACE INTO airlines (iata, name, country, type, alliance)
        VALUES (?, ?, ?, ?, ?)
        """,
        (iata, info["name"], info["country"], info["type"], info["alliance"]),
    )

connection.commit()
connection.close()
