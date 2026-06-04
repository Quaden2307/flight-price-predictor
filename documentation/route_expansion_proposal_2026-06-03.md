# Route Expansion Proposal — 2026-06-03

**Why now:** routes are the model's hard boundary (it can only predict routes it
has data for), and adding a route today means ~3 months of training data by the
August target. With no users yet, the **objectively busiest routes** are the best
available proxy for future demand. This proposes a prioritized expansion based on
2024–2025 traffic data, cross-referenced against the current 230-route list.

---

## ✅ STATUS: IMPLEMENTED — 2026-06-03 (all three tiers)

At the user's direction (prioritizing breadth/training coverage), **all of Tier 1,
Tier 2, and Tier 3 were added** — not just Tier 1. Result:

- **`routes.py`: 230 → 300 routes** (Tier 1: 23, Tier 2: 15, Tier 3: 32), 0 duplicates.
- **`airports` table: 76 → 102 codes** — `populate_airports.py` re-run; every new
  airport code was already in `airports.csv`, so no hardcoded coords were needed.
- **Smoke tests passed** after Tier 2 and Tier 3 (routes load + dupe check → CSV
  coverage → `populate_airports` → full `train_lr` pipeline clean at val 0.167 →
  `collect.py` parses). This smoke-test routine is now standard for route changes.
- **API volume: ~3,220 → ~4,200 calls/day (+30%)** → runtime grows ~30%. Limit is
  per-minute (not daily), so no wall; still worth confirming the account ceiling.
- **Committed + pushed** (commits incl. `4a54adb`).
- **First collection with 300 routes: the next 6 AM run** — starts the 3-month clock.

**⚠ PENDING — post-run city-code check:** the API may label some new international
routes with metro/city codes not yet in the `airports` table (likeliest:
**Buenos Aires `EZE`→`BUE`**, Bangkok). Airport codes are covered, but city codes
can only be verified once real offers arrive. After the first 300-route run,
re-check the new routes for `dropna`-silenced rows and patch `populate_airports.py`
(`CITY_CODES`) if needed — same failure mode as the original 91%-drop bug.

---

## 1. Current coverage (230 routes) and its thesis

The existing list has a clear **tech-hub + Canada + East-Asia** thesis: strong US
tech-hub backbone (JFK/EWR/LGA, SFO/SJC, LAX, SEA, ORD, AUS, BOS), heavy Canada,
solid Western Europe, and deep Japan/China/Korea. It **under-weights the biggest
leisure and diaspora markets**, which are the single busiest routes in NA.

## 2. Research findings — busiest routes vs. our coverage

Sources: OAG 2024 (via The Points Guy), Aerotime, Simple Flying, Daily Hive,
Indian Eagle (full links at bottom). "Seats" = scheduled both-direction seats/yr.

### US Domestic — top 10 (2024), coverage:
| Route | Seats | Covered? |
|---|---|---|
| ATL–MCO | 3.47M | ❌ |
| HNL–OGG | 3.37M | ❌ |
| LAS–LAX | 3.35M | ✅ |
| DEN–PHX | 3.21M | ❌ |
| LAX–SFO | 3.16M | ✅ |
| JFK–LAX | 3.16M | ✅ |
| LGA–ORD | 3.12M | ✅ |
| ATL–FLL | 3.00M | ❌ |
| ATL–LGA | 2.92M | ✅ |
| DEN–LAS | 2.89M | ❌ |
**Gap:** Atlanta (Delta fortress / world's busiest airport) and Hawaii are absent;
Denver under-covered.

### NA→Asia — top transpacific, coverage:
SFO–TPE (#1), LAX–TPE (#3), SEA–TPE (#8) → **no Taipei at all.** Also missing
HNL–Tokyo, and **SFO/LAX–Manila** (SFO–MNL is the busiest US-Asia route by
capacity). Japan/China/Korea well covered.

### US→India — **entirely absent.** SFO (DEL/BOM/BLR), EWR (DEL/BOM), ORD (DEL).
Largest fast-growing long-haul market; fits the tech-traveler thesis.

### US→Mexico/Caribbean/Latin America — **only 10 routes, light.**
San Juan (MCO–SJU is the #1 Latin America route, 2.3M) absent; Cancun under-covered
(missing DFW/IAH/ORD–CUN); no Caribbean leisure (PUJ/SDQ/MBJ), no GDL/SJD/PVR.

### Well-covered: Transatlantic (minor gaps MIA/IAD/ATL/DFW–LHR; IST/LIS/MUC if
expanding) and Canada (already has YYZ–YVR, the #1 domestic route in NA).

## 3. The strategic decision (broaden vs. deepen)

- **Broaden → mass-market** (Atlanta, Hawaii, Denver, Cancun, San Juan): become a
  general flight-price tool.
- **Deepen → niche** (Taipei, India, Manila, more Asia/business): stay the
  "tech/international traveler" tool the current list implies.
- **Recommendation:** Tier 1 below deliberately hits the giants in *both* camps in
  ~23 routes, so the choice can be deferred without losing the 3-month clock.

## 4. Proposed additions (paste-ready for `routes.py`)

### Tier 1 — add now (~23 routes, +~322 calls/day ≈ +10%)
```python
    # ── Hawaii (4) ──
    ("LAX","HNL"), ("SFO","HNL"), ("SEA","HNL"), ("HNL","OGG"),
    # ── Atlanta hub (4) ──
    ("ATL","MCO"), ("ATL","FLL"), ("ATL","LAX"), ("ATL","MIA"),
    # ── Taipei (3) ──
    ("SFO","TPE"), ("LAX","TPE"), ("SEA","TPE"),
    # ── US→India (5) ──
    ("SFO","DEL"), ("SFO","BOM"), ("EWR","DEL"), ("EWR","BOM"), ("ORD","DEL"),
    # ── Denver hub (3) ──
    ("DEN","PHX"), ("DEN","LAS"), ("DEN","ORD"),
    # ── Puerto Rico / Caribbean (2) ──
    ("MCO","SJU"), ("JFK","SJU"),
    # ── Manila (2) ──
    ("SFO","MNL"), ("LAX","MNL"),
```

### Tier 2 — added (15 routes)
```python
    # Cancun from southern hubs / more Mexico
    ("DFW","CUN"), ("IAH","CUN"), ("ORD","CUN"), ("LAX","GDL"), ("LAX","SJD"),
    # Middle East (Gulf carriers, premium + connecting)
    ("JFK","DXB"), ("IAD","DXB"), ("JFK","DOH"),
    # Transatlantic fill
    ("MIA","LHR"), ("IAD","LHR"), ("ATL","LHR"), ("DFW","LHR"),
    # Istanbul / Lisbon (fast-growing leisure + connecting)
    ("JFK","IST"), ("EWR","LIS"), ("JFK","LIS"),
```

### Tier 3 — added (32 routes, demand-ranked → 300 total)
```python
    # Caribbean leisure (8) — NYC/Miami dominant
    ("JFK","PUJ"), ("MIA","PUJ"), ("JFK","SDQ"), ("MIA","SDQ"),
    ("JFK","MBJ"), ("MIA","AUA"), ("BOS","SJU"), ("EWR","SJU"),
    # South America (4) — Miami hub
    ("MIA","LIM"), ("MIA","MDE"), ("JFK","EZE"), ("MIA","SCL"),
    # US domestic — Atlanta / Charlotte / Hawaii / Denver (10)
    ("ATL","DFW"), ("ATL","ORD"), ("ATL","TPA"), ("ATL","BOS"),
    ("CLT","LGA"), ("CLT","MCO"), ("LAX","OGG"), ("SFO","OGG"),
    ("DEN","SFO"), ("DEN","SEA"),
    # Secondary Asia (4)
    ("LAX","BKK"), ("SFO","BKK"), ("EWR","SIN"), ("JFK","TPE"),
    # More India (3)
    ("SFO","BLR"), ("JFK","DEL"), ("IAD","DEL"),
    # More Europe — Munich / Zurich (3)
    ("JFK","MUC"), ("ORD","MUC"), ("JFK","ZRH"),
```

**Operational step after adding:** new airport codes (HNL, OGG, TPE, DEL, BOM,
MNL, SJU, DXB, DOH, GDL, SJD, IST, LIS …) and any city codes the API returns for
them must be in the `airports` table, or `build_features`'s `dropna` will silently
drop those rows. **Re-run `populate_airports.py` and re-check coordinate coverage**
immediately after expanding (same fix as the metro-code issue).

## 5. API budget (checked 2026-06-03)

- Documented limit for `prices_for_dates` (Aviasales v3) is **60 requests/minute**
  (per-minute, **not** a daily cap); 429 on exceed; higher available on request.
- **Observed:** the collector sustains ~400 req/min (3,220 calls in ~8 min on fast
  days) with **0 rate-limit errors across 28 runs** → the account's effective limit
  is well above 60/min, or it isn't binding for this token.
- **Implication:** adding routes raises the *daily total* and *runtime*, not the
  per-minute rate (calls are sequential). Tier 1 ≈ +10% calls ≈ ~1 extra minute on
  fast days. No rate-limit risk. *(Still worth confirming the account's true
  ceiling + any monthly quota in the TravelPayouts dashboard.)*

---

## 6. Future UI idea (parked — far from UI work)

**Coverage heat map / bubble map.** A visual on the UI showing geographic coverage
density — bubbles (or a choropleth) sized/colored by how many routes/how much data
each region has. Makes it immediately obvious to users that, e.g., North America,
Western Europe, and East Asia are well covered while **Africa, the Middle East, and
South America are sparse.** Doubles as an honesty/transparency feature (consistent
with the per-estimate error-band idea): users see where predictions are
data-backed vs. thin, and it visually communicates the "request a route" expansion
story. Revisit when UI work begins.

---

## Sources
- [OAG busiest routes 2024 — The Points Guy](https://thepointsguy.com/news/busiest-airline-routes-2024-oag/)
- [US domestic busiest 2024 — Aerotime](https://www.aerotime.aero/articles/busiest-flight-routes-usa-2024)
- [NA–Asia busiest by seats — Simple Flying](https://simpleflying.com/10-busiest-routes-seats-north-america-asia/)
- [Transatlantic 2025 — Simple Flying](https://simpleflying.com/most-popular-us-europe-transatlantic-routes-2025/)
- [YYZ–YVR busiest NA domestic — Daily Hive](https://dailyhive.com/vancouver/vancouver-toronto-busiest-domestic-flight-route)
- [US–India nonstops — Indian Eagle](https://www.indianeagle.com/travelbeats/cheap-nonstop-flights-from-usa-to-india/)
- [API rate limits — Travelpayouts](https://support.travelpayouts.com/hc/en-us/articles/4402565416594-API-rate-limits)
