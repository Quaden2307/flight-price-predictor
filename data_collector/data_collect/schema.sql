-- One row per offer returned by the API. captured_at is when this script ran,
-- departure_at and return_at come from the offer itself.
CREATE TABLE offers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    captured_at TEXT NOT NULL,
    lead_time_days INTEGER,
    origin TEXT NOT NULL,            -- IATA city code (use *_airport for joins)
    destination TEXT NOT NULL,
    origin_airport TEXT,
    destination_airport TEXT,
    airline TEXT,
    flight_number TEXT,
    departure_at TEXT NOT NULL,
    return_at TEXT,
    trip_duration_days INTEGER,
    transfers INTEGER,
    return_transfers INTEGER,
    duration INTEGER,                -- minutes; round-trip total
    duration_to INTEGER,
    duration_back INTEGER,
    flight_class INTEGER DEFAULT 0,  -- 0=economy, 1=business, 2=first
    price REAL NOT NULL,
    currency TEXT,
    gate TEXT,
    link TEXT,
    raw_offer TEXT                   -- full JSON in case I missed a field above
);

CREATE INDEX idx_route_date ON offers(origin, destination, departure_at);
CREATE INDEX idx_captured ON offers(captured_at);

CREATE TABLE runs_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    api_calls INTEGER,
    offers_inserted INTEGER,
    failures INTEGER
);

-- Reference data: airports. Populated from a public dataset 
-- Used at training time to derive distance, country pair, region, hub tier.
CREATE TABLE airports (
    iata TEXT PRIMARY KEY,
    name TEXT,
    city TEXT,
    country TEXT,         -- ISO country code (e.g. 'US', 'CA', 'GB')
    latitude REAL,
    longitude REAL,
    hub_tier INTEGER      -- 1 = mega-hub, 2 = major, 3 = regional, NULL = unknown
);

-- Reference data: airlines. Populated manually or from a public dataset.
-- Used at training time to derive carrier type, alliance membership.
CREATE TABLE airlines (
    iata TEXT PRIMARY KEY,    -- 2-letter IATA carrier code (e.g. 'AA', 'BA')
    name TEXT,
    country TEXT,             -- ISO country code of the airline
    type TEXT,                -- 'legacy', 'lcc', 'hybrid', 'charter', NULL
    alliance TEXT             -- 'star', 'oneworld', 'skyteam', NULL
);
