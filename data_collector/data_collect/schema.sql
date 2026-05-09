CREATE TABLE offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    lead_time_days INTEGER,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    origin_airport TEXT,
    destination_airport TEXT,
    airline TEXT,
    flight_number TEXT,
    departure_at TEXT NOT NULL,
    transfers INTEGER,
    return_transfers INTEGER,
    duration INTEGER,
    duration_to INTEGER,
    duration_back INTEGER,
    flight_class INTEGER, 
    price REAL NOT NULL,
    currency TEXT,
    gate TEXT,
    link TEXT,
    raw_offer TEXT
);

CREATE INDEX idx_route_date ON offers(origin, destination, departure_at);
CREATE INDEX idx_captured ON offers(captured_at);
