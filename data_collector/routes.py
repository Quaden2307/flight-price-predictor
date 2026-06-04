"""
Route list for the daily collector.
300 routes = 230 original + 23 Tier-1 + 15 Tier-2 + 32 Tier-3 busiest-route expansion (2026-06-03).
See CONTEXT.md ("Route plan") and documentation/route_expansion_proposal_2026-06-03.md.
"""

ROUTES = [
    # ═══ NA-NA backbone (129) ═══

    # From YYZ (Toronto, 23)
    ("YYZ", "YVR"), ("YYZ", "YUL"), ("YYZ", "YYC"), ("YYZ", "YOW"),
    ("YYZ", "YHZ"), ("YYZ", "YEG"), ("YYZ", "JFK"), ("YYZ", "LGA"),
    ("YYZ", "EWR"), ("YYZ", "BOS"), ("YYZ", "ORD"), ("YYZ", "IAD"),
    ("YYZ", "DCA"), ("YYZ", "ATL"), ("YYZ", "MIA"), ("YYZ", "FLL"),
    ("YYZ", "MCO"), ("YYZ", "LAX"), ("YYZ", "SFO"), ("YYZ", "SEA"),
    ("YYZ", "LAS"), ("YYZ", "DFW"), ("YYZ", "PHL"),

    # From YVR (Vancouver, 11)
    ("YVR", "YUL"), ("YVR", "YYC"), ("YVR", "YEG"), ("YVR", "JFK"),
    ("YVR", "LAX"), ("YVR", "SFO"), ("YVR", "SEA"), ("YVR", "LAS"),
    ("YVR", "PDX"), ("YVR", "DEN"), ("YVR", "PHX"),

    # From YUL (Montreal, 9)
    ("YUL", "YYC"), ("YUL", "YOW"), ("YUL", "JFK"), ("YUL", "LGA"),
    ("YUL", "EWR"), ("YUL", "BOS"), ("YUL", "MIA"), ("YUL", "FLL"),
    ("YUL", "LAX"),

    # From YYC (Calgary, 6)
    ("YYC", "YEG"), ("YYC", "LAX"), ("YYC", "SFO"), ("YYC", "SEA"),
    ("YYC", "LAS"), ("YYC", "PHX"),

    # From YOW (Ottawa, 2) — for school/grad-network marketing
    ("YOW", "LGA"), ("YOW", "MCO"),

    # From JFK (NYC, 20)
    ("JFK", "LAX"), ("JFK", "SFO"), ("JFK", "SEA"), ("JFK", "MIA"),
    ("JFK", "FLL"), ("JFK", "BOS"), ("JFK", "ORD"), ("JFK", "LAS"),
    ("JFK", "DEN"), ("JFK", "ATL"), ("JFK", "DFW"), ("JFK", "IAD"),
    ("JFK", "MCO"), ("JFK", "AUS"), ("JFK", "PHX"),
    ("JFK", "MSP"), ("JFK", "RDU"), ("JFK", "PHL"), ("JFK", "DTW"),
    ("JFK", "IAH"),

    # From EWR / LGA (NYC area, 9)
    ("EWR", "LAX"), ("EWR", "SFO"), ("EWR", "MIA"), ("EWR", "ORD"),
    ("LGA", "MIA"), ("LGA", "MCO"), ("LGA", "ATL"), ("LGA", "ORD"),
    ("LGA", "DFW"),

    # From SFO (Bay Area, 14)
    ("SFO", "LAX"), ("SFO", "SAN"), ("SFO", "SEA"), ("SFO", "PDX"),
    ("SFO", "LAS"), ("SFO", "DEN"), ("SFO", "ORD"), ("SFO", "BOS"),
    ("SFO", "MIA"), ("SFO", "AUS"),
    ("SFO", "MSP"), ("SFO", "RDU"), ("SFO", "IAH"), ("SFO", "CLT"),

    # From SJC (Silicon Valley, 8)
    ("SJC", "SEA"), ("SJC", "LAX"), ("SJC", "JFK"), ("SJC", "ORD"),
    ("SJC", "DEN"), ("SJC", "AUS"), ("SJC", "LAS"), ("SJC", "PHX"),

    # From LAX (11)
    ("LAX", "SEA"), ("LAX", "LAS"), ("LAX", "DEN"), ("LAX", "PHX"),
    ("LAX", "AUS"), ("LAX", "DFW"), ("LAX", "ORD"), ("LAX", "MIA"),
    ("LAX", "MCO"), ("LAX", "PDX"), ("LAX", "SAN"),

    # From SEA (8)
    ("SEA", "LAS"), ("SEA", "DEN"), ("SEA", "ORD"), ("SEA", "PDX"),
    ("SEA", "AUS"), ("SEA", "DFW"), ("SEA", "MSP"), ("SEA", "RDU"),

    # From ORD (Chicago, 6)
    ("ORD", "DFW"), ("ORD", "MIA"), ("ORD", "MSP"), ("ORD", "DTW"),
    ("ORD", "RDU"), ("ORD", "IAH"),

    # Other US tech-hub interconnections (4)
    ("AUS", "DFW"), ("ATL", "RDU"), ("ATL", "CLT"), ("BOS", "DCA"),

    # ═══ NA-International (75) ═══

    # NA → Western Europe (42)
    ("JFK", "LHR"), ("JFK", "CDG"), ("JFK", "AMS"), ("JFK", "FRA"),
    ("JFK", "MAD"), ("JFK", "DUB"), ("JFK", "FCO"), ("JFK", "BCN"), ("JFK", "BER"),
    ("EWR", "LHR"), ("EWR", "CDG"), ("EWR", "AMS"), ("EWR", "FRA"),
    ("EWR", "BCN"), ("EWR", "BER"),
    ("SFO", "LHR"), ("SFO", "CDG"), ("SFO", "AMS"), ("SFO", "FRA"),
    ("LAX", "LHR"), ("LAX", "CDG"), ("LAX", "AMS"), ("LAX", "FRA"),
    ("ORD", "LHR"), ("ORD", "CDG"), ("ORD", "AMS"), ("ORD", "FRA"),
    ("ORD", "BCN"), ("ORD", "BER"),
    ("BOS", "LHR"), ("BOS", "CDG"), ("BOS", "AMS"), ("BOS", "DUB"), ("BOS", "BCN"),
    ("YYZ", "LHR"), ("YYZ", "CDG"), ("YYZ", "AMS"), ("YYZ", "FRA"),
    ("YVR", "LHR"), ("YVR", "CDG"),
    ("YUL", "LHR"), ("YUL", "CDG"),

    # NA → Japan (11)
    ("JFK", "NRT"),
    ("SFO", "NRT"), ("SFO", "HND"),
    ("LAX", "NRT"), ("LAX", "HND"),
    ("ORD", "NRT"),
    ("SEA", "NRT"), ("SEA", "HND"),
    ("YYZ", "NRT"), ("YYZ", "HND"), ("YVR", "NRT"),

    # NA → China (19)
    ("JFK", "PEK"), ("JFK", "PVG"), ("JFK", "HKG"),
    ("EWR", "PVG"),
    ("SFO", "PVG"), ("SFO", "PEK"), ("SFO", "HKG"),
    ("LAX", "HKG"), ("LAX", "PVG"), ("LAX", "PEK"),
    ("ORD", "PEK"), ("ORD", "PVG"),
    ("SEA", "PEK"), ("SEA", "PVG"), ("SEA", "HKG"),
    ("YYZ", "HKG"), ("YYZ", "PEK"), ("YYZ", "PVG"),
    ("YVR", "PVG"),

    # NA → South Korea (7)
    ("JFK", "ICN"),
    ("SFO", "ICN"), ("LAX", "ICN"), ("SEA", "ICN"),
    ("ORD", "ICN"), ("YYZ", "ICN"), ("YVR", "ICN"),

    # NA → Singapore (2)
    ("SFO", "SIN"), ("LAX", "SIN"),

    # NA → Latin America (10)
    ("JFK", "MEX"), ("JFK", "CUN"), ("JFK", "BOG"), ("JFK", "GRU"),
    ("LAX", "MEX"), ("LAX", "CUN"),
    ("MIA", "MEX"), ("MIA", "CUN"), ("MIA", "BOG"), ("MIA", "GRU"),

    # ═══ Intra-East-Asia (8) ═══
    # Multi-country Asia trip legs (e.g., NA traveler doing NYC→NRT→ICN→NYC).
    # Cache may be thinner than NA routes since market=us biases collection
    # toward US-originated searches. Expect data to accumulate slower.

    # Japan ↔ Korea (2)
    ("NRT", "ICN"), ("HND", "ICN"),

    # Japan ↔ China (incl. Hong Kong) (3)
    ("NRT", "PVG"), ("NRT", "PEK"), ("NRT", "HKG"),

    # Korea ↔ China (incl. Hong Kong) (3)
    ("ICN", "PVG"), ("ICN", "PEK"), ("ICN", "HKG"),

    # ═══ Tier-1 expansion (23) — added 2026-06-03 ═══
    # Busiest-route gaps from documentation/route_expansion_proposal_2026-06-03.md.
    # NOTE: re-run populate_airports.py after this so new airport/city codes get
    # coordinates, else build_features' dropna silently drops these rows.

    # Hawaii (4)
    ("LAX", "HNL"), ("SFO", "HNL"), ("SEA", "HNL"), ("HNL", "OGG"),

    # Atlanta hub (4)
    ("ATL", "MCO"), ("ATL", "FLL"), ("ATL", "LAX"), ("ATL", "MIA"),

    # Taipei (3)
    ("SFO", "TPE"), ("LAX", "TPE"), ("SEA", "TPE"),

    # US → India (5)
    ("SFO", "DEL"), ("SFO", "BOM"), ("EWR", "DEL"), ("EWR", "BOM"), ("ORD", "DEL"),

    # Denver hub (3)
    ("DEN", "PHX"), ("DEN", "LAS"), ("DEN", "ORD"),

    # Puerto Rico / Caribbean (2)
    ("MCO", "SJU"), ("JFK", "SJU"),

    # Manila (2)
    ("SFO", "MNL"), ("LAX", "MNL"),

    # ═══ Tier-2 expansion (15) — added 2026-06-03 ═══
    # Mexico/Caribbean leisure, Gulf carriers, transatlantic fill, IST/LIS.

    # Cancun from southern hubs + more Mexico (5)
    ("DFW", "CUN"), ("IAH", "CUN"), ("ORD", "CUN"), ("LAX", "GDL"), ("LAX", "SJD"),

    # Middle East — Gulf carriers (3)
    ("JFK", "DXB"), ("IAD", "DXB"), ("JFK", "DOH"),

    # Transatlantic fill (4)
    ("MIA", "LHR"), ("IAD", "LHR"), ("ATL", "LHR"), ("DFW", "LHR"),

    # Istanbul / Lisbon (3)
    ("JFK", "IST"), ("EWR", "LIS"), ("JFK", "LIS"),

    # ═══ Tier-3 expansion (32) — added 2026-06-03 ═══
    # Next-busiest, demand-ranked → brings total to 300. Caribbean/LatAm leisure
    # (Punta Cana, Santo Domingo, Montego Bay, Lima, Medellín), Atlanta/Charlotte/
    # Hawaii/Denver domestic, secondary Asia/India/Europe.

    # Caribbean leisure (8) — NYC/Miami dominant
    ("JFK", "PUJ"), ("MIA", "PUJ"), ("JFK", "SDQ"), ("MIA", "SDQ"),
    ("JFK", "MBJ"), ("MIA", "AUA"), ("BOS", "SJU"), ("EWR", "SJU"),

    # South America (4) — Miami hub
    ("MIA", "LIM"), ("MIA", "MDE"), ("JFK", "EZE"), ("MIA", "SCL"),

    # US domestic — Atlanta / Charlotte / Hawaii / Denver (10)
    ("ATL", "DFW"), ("ATL", "ORD"), ("ATL", "TPA"), ("ATL", "BOS"),
    ("CLT", "LGA"), ("CLT", "MCO"), ("LAX", "OGG"), ("SFO", "OGG"),
    ("DEN", "SFO"), ("DEN", "SEA"),

    # Secondary Asia (4)
    ("LAX", "BKK"), ("SFO", "BKK"), ("EWR", "SIN"), ("JFK", "TPE"),

    # More India (3)
    ("SFO", "BLR"), ("JFK", "DEL"), ("IAD", "DEL"),

    # More Europe — Munich / Zurich (3)
    ("JFK", "MUC"), ("ORD", "MUC"), ("JFK", "ZRH"),
]
