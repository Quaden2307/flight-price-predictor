# Pre-Modeling Checklist

Tracking the structural work that needs to happen before I start training. Target start date for modeling: ~2026-05-31 (two-week buffer to keep accumulating data and learn ML fundamentals deeper).

---

## Action items

### 1. Run notebook 04 and lock in the airline_type findings
Status: done 2026-05-17. Three plots reviewed (see plots_observations_phase2 #8-10). Key conclusions:
- LCC vs not-LCC is the only strong split in airline_type. Hybrid vs legacy adds little.
- Within-type variance is large (CX ~$1300 vs SC ~$300, both "legacy") because type is partially proxying for route mix, not pure pricing strategy.
- airline itself needs to be a feature, not just airline_type.

### 2. Three small feature-question plots
Status: TODO. ~30 min each, each either earns a feature a spot in the model or rules it out.

- **Price by day-of-week of departure** — does Tuesday cost less? Need to extract day_of_week from departure_at first. If yes, add as a feature.
- **Price by number of transfers (0 direct, 1 connection, 2+ multi-stop)** — direct flights probably cost more on short routes. Adds transfers as a feature.
- **Trip duration vs price** — does a 2-day round trip cost less than a 14-day round trip on the same route? Tests whether trip_duration_days matters.

### 3. Sanity check duplicates one more time
Status: TODO. After all the merging activity (countries, lat/long, airline_type), re-run the dup-check query I did earlier:
- Group by (captured_at, origin_airport, destination_airport, departure_at, return_at, airline, flight_number, price) and look for groups with count > 1.
- Already verified once on 2026-05-12 (the apparent duplicates were legit same-outbound-different-return round-trip pairs). Worth re-confirming after the additional joins.

### 4. Target variable decision
Status: leaning toward `log(price)` for v1.
- Raw price: distance dominates, model mostly learns "long flight = expensive." Weak.
- log(price): handles right-skewed distribution. Standard for price prediction. Good v1 choice.
- Price relative to route mean: removes the distance effect, focuses on within-route fluctuations. Cleaner target but harder to interpret. Consider for v2.
- "Should I book now vs wait" (classification): not a model target — it's a product-layer derivation FROM a price model. Train price prediction, then at inference time query the model twice (today's lead_time vs future lead_time on same flight) and compare. The model output stays interpretable; the recommendation logic lives in product code.

Plan for v1: predict `log(price)`. Add `route_mean_log_price` as a FEATURE (not target) so the model can learn "this flight vs typical for the route." Get the route-relative signal without the weird target.

### 5. Train/val/test split decision
Status: TODO. Critical and easy to get wrong.
- Random split is wrong — leaks future-snapshot info into training.
- By `captured_at`: train on earliest snapshots, test on latest. Right for "today's prediction for today's price."
- By `departure_at`: train on flights departing before some date, test on flights departing after. Right for "user searches for a future flight, model predicts price."

Plan: split by `departure_at`. Matches the real deployment scenario (user inputs a future flight). Need src/split.py to encapsulate the logic.

### 6. Build src/features.py
Status: skeleton file created 2026-05-17 (imports only). Need to add:
- A `build_features(offers_df, airports_df, airlines_df)` function that returns the modeling DataFrame.
- All the transformations currently in the notebook: country merges → is_international, lat/long merges → distance_km, airline merge → airline_type.
- Derived columns: day_of_week, month_of_year, route_mean_log_price (computed on the training subset, then merged into val/test to avoid leakage).
- This becomes the single source of truth for what the model is trained on.

### 7. Build src/split.py
Status: TODO. Small helper that returns train/val/test indices given the split strategy from item 5. Once built, both training and evaluation use it.

---

## Two-week plan

- **Week 1 (May 17-23)**: items 2 and 3 above (small plots, dup check). Continue collecting daily data. Learn decision trees and random forests in parallel — read the relevant chapters of whichever ML resource I'm using, work through a small toy problem with sklearn on the side.
- **Week 2 (May 24-30)**: items 4-7 (target decision, split strategy, features.py, split.py). Should not start actually training until features.py and split.py are both done.
- **Target modeling start: 2026-05-31.** By then I'll have ~24 days of data (~96K rows) and the structural setup will be ready.

The point of the buffer is to NOT rush. Models can fail in subtle ways if the data pipeline isn't right, and debugging "is this a model bug or a data bug" is much harder than getting the data right first.
