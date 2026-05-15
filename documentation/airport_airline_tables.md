# Populating the airports and airlines tables

Both tables already exist in flights.db with the right schema but are empty. Filling them is a one-time setup task that unlocks two important feature-engineering primitives the model is going to need.

---

## Why now

Looking at the price-vs-lead-time scatterplot for the live data, the dense band has no obvious slope — prices don't visibly rise as lead time shrinks. That isn't because lead time doesn't matter; it's because the bimodal price distribution (domestic short-haul vs international long-haul) is washing out any within-route signal. Without features that distinguish those two regimes, the visualizations stay muddled and any model trained on raw columns will split the difference between them.

Two specific features fix this and both need the airports table:

- **distance_km**: great-circle distance between origin and destination. Captures the single strongest predictor of price. Without it, the model can't tell YYZ-LHR (~6000 km) apart from YYZ-ORD (~700 km) except through airline patterns, which is noisy.
- **is_international**: boolean flag derived by comparing the country column for origin vs destination airports. Cleanly separates the two clusters in the price histogram.

Both fall out of the airports table for free once it's populated. No hardcoding, no per-route distance arrays — and importantly, the same code path works for arbitrary user input later, not just the 53 airports currently in ROUTES. That matters for v1's cold-start UX (users searching unseen routes).

The airlines table is a smaller win but worth doing in the same batch since I'll already be in data-loading mode: lets me tag carriers as legacy/lcc/hybrid and (eventually) by alliance, which becomes useful for the LCC-vs-legacy pricing regime discussed in the Phase 1 EDA notes.

---

## What the airports table will hold

Schema is already there:

```sql
CREATE TABLE airports (iata TEXT PRIMARY KEY, name TEXT, city TEXT,
                       country TEXT, latitude REAL, longitude REAL, hub_tier INTEGER);
```

Populate from a public airports reference dataset (filter to only the ~53 IATA codes that appear in ROUTES — no need to load tens of thousands of rows). hub_tier won't come from the public dataset; fill it manually later from passenger-volume data, or leave NULL for now and add a default tier based on the CBRE tech-talent rankings in CONTEXT.md.

Approach: small helper script in data_collector/ that pulls the source CSV, filters by iata code, and inserts into the airports table. Run it once. Re-runnable if I expand ROUTES later.

---

## What the airlines table will hold

Get the initial carrier list from the data already collected:

```sql
SELECT DISTINCT airline FROM offers ORDER BY airline;
```

Last check showed ~100 distinct airline codes. Manually look up each for country, type (legacy / lcc / hybrid), and alliance (star / oneworld / skyteam / none). Tedious but one-time, and 100 rows is manageable. Could split into a "core 30" pass first and fill the long tail later.

---

## Using the new features

Once the airports table has data, distance is a haversine calculation between the two coordinate pairs. Either roll the formula by hand using the standard math module (radians, sin, cos, asin, sqrt — six lines) or pull in a small geo library that exposes it as a one-line helper. Going with the hand-rolled version is more instructive and avoids another dependency for something this small.

is_international is even simpler: join offers to airports twice (once for origin, once for destination) and compare the country columns. Can be done at query time or computed once as a derived column when building the modeling DataFrame.

---

## Order of operations

1. Write a small loader script for airports — download, filter, insert.
2. Verify with a quick SELECT — all 53 codes present, lat/long sane.
3. Add a distance helper (haversine) that takes two IATA codes and returns km.
4. Add an is_international helper / SQL view.
5. Re-run the EDA notebook with distance and is_international as new columns. Expect the bimodal price distribution to map cleanly onto the is_international flag, and the price-vs-lead-time scatter to show a slope once faceted by distance bucket.
6. Loader script for airlines, populated semi-manually from the carrier list in offers.

Each step is small and reversible — wipe the table and re-run if anything looks off.

---

## Update — airports table done

Wrote populate_airports.py and ran it. The script reads the public airports CSV row by row with csv.DictReader, filters to the IATA codes that appear in ROUTES (flattened into a set for O(1) lookup), casts lat/long to float, and inserts into the airports table. Used INSERT OR REPLACE instead of plain INSERT so re-runs don't crash on the PRIMARY KEY constraint, and wrapped the ALTER TABLE statement in a try/except since SQLite has no "ADD COLUMN IF NOT EXISTS" — that combo makes the script fully idempotent.

55 airports loaded, not the 53 I'd estimated. Turns out routes.py has grown to 230 routes since CONTEXT.md was written, so the unique-airport count is a bit higher. Country distribution looks right (28 US, 7 CA, then a long tail across Europe, East Asia, Latin America). Lat/long values resolve to the correct cities when spot-checked.

Decided to also pull the type column from the CSV into a new airport_type column on the airports table, on the theory it could be a free first pass at hub_tier. That turned out to be a bust — every single one of the 55 airports is classified as "large_airport" in the public dataset, so the column has zero discriminative value for this route mix. Leaving the column in for now since it costs nothing, but hub_tier still needs to be filled manually from passenger-volume data later if I want it.

Next step is the haversine distance helper, which uses the lat/long columns directly. is_international after that.
