# Flight Price Predictor

End-to-end flight price prediction system covering 200+ routes across 55+ airports in North America, Europe, and Asia.

Two phases: an automated data pipeline (running daily) and an XGBoost price model (in active development in a separate private repo). The pipeline has been live since early May 2026 and has accumulated 60,000+ flight offers across 16 daily runs so far. Modeling work is informed by ~18 plots of documented EDA across two data phases.

This public repo covers the data pipeline, feature engineering, and EDA. Model training code and trained artifacts are kept private.

![System architecture](diagrams/architecture.svg)

![Flight Predictor overview](diagrams/Flight%20Predictor.jpeg)

---

## Status

| Component | Status |
|---|---|
| Data pipeline — domestic (Phase 1) | Complete |
| Data pipeline — live international (Phase 2) | Complete |
| Data-quality scripts (dedup + integrity check) | Complete |
| EDA — Phase 1 (domestic US) | Complete |
| EDA — Phase 2 (live international) | Complete |
| Feature engineering (`src/features.py`) | In progress |
| Train/val/test split (`src/split.py`) | Planned |
| XGBoost model training | In progress (separate private repo) |
| Prediction API / frontend | Planned |

Target modeling start: end of May 2026, once feature engineering and the split strategy are locked in. Goal metric: MAPE on a held-out test set, targeting sub-10%. Will update with the measured number once a baseline is in place.

---

## Tech Stack

- **Pipeline:** Python, SQLite, `requests`
- **Processing:** Pandas, NumPy
- **Modeling:** Scikit-learn, XGBoost
- **Visualization:** Matplotlib, Seaborn
- **Notebooks:** Jupyter

---

## Project Structure

```
flight-price-predictor/
├── data_collector/                # Daily ingestion pipeline
│   ├── collect.py                 # Main collector — calls the API, writes to SQLite
│   ├── dedupe.py                  # Exact-key duplicate guard (9-column key)
│   ├── integrity_check.py         # Daily NULL/range/volume audit
│   ├── routes.py                  # 200+ origin-destination pairs to query
│   ├── schema.sql                 # Database schema
│   ├── populate_airports.py       # One-time airport reference table loader
│   └── populate_airlines.py       # One-time airline reference table loader
├── notebooks/                     # EDA notebooks
│   ├── 01_data_exploration.ipynb
│   ├── 02_data_visualization.ipynb        # Phase 1 EDA (domestic)
│   ├── 03_live_data_visualization.ipynb   # Phase 2 EDA (live international)
│   └── 04_airline_analysis.ipynb
├── src/                           # Feature engineering and modeling code
│   ├── features.py                # build_features() — single source of truth
│   └── ...                        # split.py, model.py, train.py (in progress)
├── documentation/                 # Design notes, checklists, daily run logs
├── plots_observations             # EDA findings — Phase 1
├── plots_observations_phase2      # EDA findings — Phase 2
├── data/                          # SQLite DB (gitignored)
└── requirements.txt
```

---

## Data Pipeline

The pipeline runs daily via launchd, pulling round-trip flight offers from a commercial pricing API and writing them to a local SQLite database. One row per offer.

**What it does each day:**
- ~3,200 API calls per run (200+ routes × 7 departure months × 2 trip-duration offsets)
- ~4,000 offers inserted per day
- Retry-with-backoff on `RequestException` — 3 attempts, exponential backoff starting at 2s. Has cleanly handled multiple slow-API days with zero final failures.
- Per-run logging to a `runs_logs` table (start/finish, calls, inserts, failures)
- Daily backup of the SQLite file to a cloud folder

**Post-collection data-quality checks** (`dedupe.py`, `integrity_check.py`):
- 9-column exact-key dedup guard (dry-run by default; `--apply` to delete)
- NULL audit on modeling-critical columns (`price`, `airline`, `departure_at`, `return_at`, `trip_duration_days`, `lead_time_days`)
- Range audit (impossible values like negative prices or trip durations >365 days)
- Volume-drop detection (flags days >25% below a 3-day rolling baseline)
- Exits non-zero on any anomaly so launchd's stderr log captures the alert

**To run the collector:**

```bash
pip install -r requirements.txt

# In data_collector/.env, set:
#   API_TOKEN=<your token>
#   API_URL=<your endpoint>
#   BACKUP_PATH=<optional cloud-synced path>

python data_collector/collect.py
```

A single run takes ~8 minutes when the upstream API is responsive, ~5–6 hours on slow-API days. The retry logic handles transient failures without intervention.

---

## EDA — Key Findings

~18 documented plots across two phases. The findings that shaped the model design:

**Phase 1 (domestic US):**
- Fare distribution is right-skewed — log-transformed target is the right move
- Distance is the strongest single predictor, but the relationship is sublinear
- LCC vs. legacy carriers create two distinct fare regimes at short distances
- Market share is confounded with distance — both features needed

**Phase 2 (live international):**
- Price distribution is bimodal — short-haul domestic cluster and long-haul international cluster
- `is_international` is a coarse proxy for distance; distance itself is the real driver
- Day-of-week matters for international (vacation premium around weekends), mostly flat for domestic
- Direct-flight premium is real and distance-independent — `transfers` adds signal beyond distance
- Lead time matters mainly for long-haul; weak signal on short/medium routes
- Same-flight day-over-day prices barely move — only ~5.6% of flights ever changed price across an 11-day capture window. Most observed price variation comes from the offer set churning (new flights appearing, old ones falling out), not from real price movement. Shapes the target framing: predict the price of a flight appearing on day X, not how a known flight's price will change.

---

## Modeling Approach

**Target:** `log(price)`. Standard for right-skewed price data and keeps loss interpretable in percentage terms once exponentiated.

**Features (planned):**
- `distance_km` — strongest predictor, sublinear shape
- `lead_time_days` — weak on short routes, real signal on long-haul
- `day_of_week` — meaningful for international routes
- `month_of_year` — captures seasonality
- `airline_type` (LCC / hybrid / legacy) — `is_lcc` captures most of the signal
- `airline` — within-type variance is large, so airline itself is needed as a feature
- `transfers` — independent of distance
- `is_international` — coarse but cheap backup signal
- `route_mean_log_price` — per-route mean of log-price, fit on training data only to avoid leakage

**Model:** XGBoost. Chosen for native handling of the LCC/legacy regime split and the sublinear distance relationship without manual feature crossing, plus native handling of high-cardinality categoricals (airline, origin, destination). Training code and trained artifacts live in a separate private repository.

**Evaluation:** MAPE on a held-out test set, stratified by distance bucket. Targeting sub-10%.

**Train/val/test split:** by `departure_at`, not random. The deployment scenario is a user querying a future flight, so the training set must not see flights departing after the test window. Random splits would leak future-snapshot info into training and overstate the score.

---

## Dataset & Model Artifacts

The SQLite database is gitignored (~70MB and growing); the collector regenerates it from scratch given an API key, though cumulative dataset depth has to be built up over time at ~4K rows/day.

The trained model, training scripts, and evaluation notebooks live in a separate private repository. This public repo is scoped to the data infrastructure, feature engineering, and EDA findings that shaped the model design.
