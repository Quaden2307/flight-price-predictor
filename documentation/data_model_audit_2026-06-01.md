# Data & Modeling Audit — 2026-06-01

**Purpose.** A factual record of an investigation into the flight-price model. It
separates *observations* (measured facts) from *interpretation* (tentative,
possibly wrong) so the findings can be evaluated independently. Recommendations
are deliberately minimal and labeled as options, not conclusions.

All numbers below are from single runs (one seed, one split each) unless stated;
they have **no confidence intervals** and should be re-verified before being
relied on. Reproduction snippets are in the last section.

---

## 0. Context (as of this audit)

- **Goal:** predict flight `price`; stated target val MAPE < 0.12 by 2026-08-01.
- **Data:** `data/flights.db`, table `offers`, 97,608 rows. Collected daily since
  ~2026-05-10 via a round-trip pricing API (`one_way=false`), economy only,
  querying 7 departure months ahead each day.
- **Feature set "baseline-v1"** (in `src/features.py`): numeric `distance_km`,
  `lead_time_days`, `transfers`, `is_international`, `route_mean_log_price`;
  one-hot `airline`, `airline_type`, `day_of_week`, `month_of_year`. Target =
  `log_price`. After one-hot, 131 columns (126 are dummies; `airline` has 120
  distinct values).
- **Split (in `src/split.py`):** chronological by `departure_at`, quantile
  cutoffs 0.70 / 0.85 → train / val / test.
- **Evaluation:** MAPE in dollar space (predictions and targets exponentiated
  from log).
- A prior coverage fix this session raised the `airports` table from 55 → 76
  codes (added metro/city codes the API returns), which moved the *trained*
  matrix from ~6k to ~68k rows. Modeling runs #1–3 in `modeling_runs.md` predate
  that fix (biased ~6k subset); runs #4–6 are post-fix.

Post-fix modeling runs already logged (chronological split, baseline-v1):

| Run | Model | Train MAPE | Val MAPE |
|---|---|---|---|
| 4 | LR (defaults) | 0.175 | 0.166 |
| 5 | XGB (n300/d6/lr.1/ss.8/cs.8) | 0.117 | 0.181 |
| 6 | XGB sweep (best of 18) | 0.122 | 0.178 |

---

## 1. Observations — data structure

- **Round-trip data.** Every offer has a return (`return_at` 0% null,
  `trip_duration_days` 0% null). `trip_duration_days` mean 8.0, std 7.8, range
  0–58. Collector caps trips at ~60 days (API limit).
- **One unit, one class.** `currency` = `usd` for all 97,608 rows.
  `flight_class` = 0 (economy) for all rows.
- **Re-collection structure.** 97,608 rows correspond to **14,613 distinct
  flights** (key = origin, destination, departure_at, flight_number, airline);
  mean 6.7 rows/flight, max 55. Each flight is re-observed on multiple capture
  dates at decreasing lead times.
- **Exact duplicate rows:** 1,104 rows share the same flight key + `captured_at`
  + `price`.
- **Two location codings exist.** `origin`/`destination` hold **city/metro
  codes** (e.g. YTO, NYC, TYO); `origin_airport`/`destination_airport` hold
  **specific airport codes** (e.g. YYZ) and are **0% null**. There are 67
  distinct airport codes across those columns; 8 are absent from the `airports`
  table (BUR, CLD, DAL, HHN, NLU, SNA, TLC, ZYA). The feature pipeline currently
  joins coordinates on the *city* code, not the airport code.
- **Columns not used as features:** `duration`, `duration_to`, `duration_back`,
  `return_transfers`, `trip_duration_days`, `gate`, `origin_airport`,
  `destination_airport`, `flight_number`, `return_at`.

---

## 2. Observations — feature signal

Correlation with `log_price` (Pearson), full data:

| Column | corr | In baseline-v1? |
|---|---|---|
| `duration` | +0.724 | no |
| `return_transfers` | +0.492 | no |
| `transfers` | +0.491 | yes |
| `trip_duration_days` | +0.299 | no |
| `lead_time_days` | +0.115 | yes |

Binned mean price (shape; non-linearities):

- **vs `lead_time_days`:** non-monotonic — ~$474–499 at 0–14 days, rising to ~$594
  at 60–90, dipping ~$558 at 90–150, ~$623 at 150–250.
- **vs `trip_duration_days`:** ~$358–391 at 0–2 days, rising to ~$704–753 at
  10–21 days, ~$748 at 21–60 (rise-then-plateau).

---

## 3. Observations — lead-time distribution by chronological split

| Split | min | p50 | max | mean |
|---|---|---|---|---|
| train | 0 | 19 | 72 | 23.0 |
| val | 50 | 79 | 113 | 79.0 |
| test | 91 | 132 | 213 | 135.5 |

The ranges overlap minimally; test (91–213) lies entirely above train's max (72).
Mechanism: collection history is short (~3 weeks), so far-future departures have
only been observed at long lead times. A chronological split on `departure_at`
therefore separates the data largely by lead time as well.

---

## 4. Experiment A — model ranking under two split designs

Same feature set (baseline-v1), same models. Only the split differs.

- **Chronological** (`split.py`, departure_at quantiles 0.70/0.85):
  - LR: val 0.166 (train 0.175)
  - XGB (n300/d6/lr.1/ss.8/cs.8): val 0.181 (train 0.117)
- **Grouped-random** (`GroupShuffleSplit`, test_size 0.20, seed 42; groups =
  flight key, so all observations of a flight stay on one side — controls the
  re-collection leakage from §1):
  - LR: val 0.180 (train 0.173)
  - XGB (same params): val **0.141** (train 0.114)
  - Lead-time p50/max ≈ equal across train/val (33 / ~212 both sides).

**The model ranking reverses between the two splits.** Under chronological, LR <
XGB (LR better); under grouped-random, XGB < LR (XGB better), by 0.039.

Single seed / single split each — not yet repeated across seeds or folds.

---

## 5. Experiment B — signal in the unused itinerary numbers

XGB (same params) under the grouped-random split, using **only** raw numeric
columns (no route, no airline, no `route_mean_log_price`):

| Features | Val MAPE |
|---|---|
| `lead_time_days` | 0.549 |
| + `transfers`, `return_transfers` | 0.440 |
| + `trip_duration_days` | 0.402 |
| + `duration`, `duration_to`, `duration_back` | 0.173 |

For reference, the full baseline-v1 set under the same split scored LR 0.180 /
XGB 0.141. The largest single drop comes from adding `duration` (0.402 → 0.173).

---

## 6. Interpretations (tentative — may be wrong)

These are hypotheses consistent with §1–5, not established conclusions.

- **Split design changes which model looks better.** Two standard explanations:
  (a) tree models predict constants outside their training feature range, so the
  chronological split's lead-time gap (§3) penalizes them where a linear fit
  extrapolates; (b) the two splits simply measure different things —
  chronological ≈ "generalize to later-departing flights" (currently entangled
  with long lead times), grouped-random ≈ "generalize to other flights in the
  same period." Both are legitimate questions; which is "correct" depends on the
  intended use. The reversal could also be partly seed/variance — not yet tested.
- **The chronological lead-time gap may be a temporary, young-data artifact.** As
  collection continues, far-departure flights will also be observed at short lead
  times, which would shrink the train/val lead-time gap. Not verified.
- **Several high-correlation columns are unused** (§2, §5). Adding them could
  improve either or both models; the non-linear shapes (§2) are the kind tree
  models can exploit without manual transforms, while a linear model would need
  explicit transforms/binning.
- **`route_mean_log_price`** is a train-fitted target encoding; on the training
  set each row contributes to its own route mean (no out-of-fold). This can
  inflate apparent train fit. Affects both models; magnitude not measured.
- **`distance_km` is one-way great-circle**, but price is round-trip; `duration`
  may be a better proxy for trip "size."

---

## 7. Open questions / not yet checked

- Does the grouped-random XGB > LR result hold across **multiple seeds / CV
  folds**? (Only seed 42, one split tested.)
- Is `duration` (and other itinerary detail) **available at prediction time**?
  This depends on the deployment target. A decision was recorded this session to
  pursue a **tiered** approach (itinerary-level model first, route+date model as
  a later track); under the itinerary-level framing these columns are inputs,
  under a route+date framing some would be unavailable.
- How much do the **1,104 exact duplicates** and the 6.7× re-collection weighting
  affect fit and metrics?
- Is **MAPE** stable given low-price denominators? (Min price / distribution tail
  not audited here.)
- Would switching coordinate joins to `origin_airport`/`destination_airport`
  (real airports) change `distance_km` / `is_international` materially vs the
  current city-centroid approximation?
- No hyperparameter search was done under the grouped-random split (Experiment A
  used fixed params; the §6 of `modeling_runs.md` sweep was chronological).

---

## 8. Reproduction

Environment: project venv, run from repo root. Data = `data/flights.db` at
97,608 rows, `airports` table at 76 codes (post coverage-fix).

```python
# shared loaders
from src.train_lr import load_raw, prepare_xy
from src.features import build_features
from src.split import split_offers
import numpy as np, pandas as pd
from sklearn.model_selection import GroupShuffleSplit
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error as MAPE
from xgboost import XGBRegressor

offers, airports, airlines = load_raw()

# §2 correlations
o = offers.copy(); o['lp'] = np.log(o['price'])
for c in ['duration','return_transfers','transfers','trip_duration_days','lead_time_days']:
    print(c, o['lp'].corr(o[c]))

# §3 lead-time by chronological split
tr, va, te = split_offers(offers)
for n,d in [('train',tr),('val',va),('test',te)]:
    print(n, d['lead_time_days'].describe()[['min','50%','max','mean']].tolist())

# §4 grouped-random split (groups = flight key)
key = (offers['origin']+'|'+offers['destination']+'|'+offers['departure_at']+'|'
       +offers['flight_number'].astype(str)+'|'+offers['airline'])
tri, vai = next(GroupShuffleSplit(1, test_size=0.2, random_state=42).split(offers, groups=key))
trdf, rm = build_features(offers.iloc[tri], airports, airlines, route_means=None)
vadf, _  = build_features(offers.iloc[vai], airports, airlines, route_means=rm)
Xtr,ytr,cols = prepare_xy(trdf, None); Xva,yva,_ = prepare_xy(vadf, cols)
m = lambda mdl,X,y: MAPE(np.exp(y), np.exp(mdl.predict(X)))
lr  = LinearRegression().fit(Xtr,ytr)
xgb = XGBRegressor(n_estimators=300,max_depth=6,learning_rate=0.1,subsample=0.8,
                   colsample_bytree=0.8,random_state=42,n_jobs=-1).fit(Xtr,ytr)
print('LR', m(lr,Xva,yva), 'XGB', m(xgb,Xva,yva))

# §5 raw-numeric headroom (same grouped split, XGB)
y = np.log(offers['price'])
for feats in (['lead_time_days'],
              ['lead_time_days','transfers','return_transfers'],
              ['lead_time_days','transfers','return_transfers','trip_duration_days'],
              ['lead_time_days','transfers','return_transfers','trip_duration_days',
               'duration','duration_to','duration_back']):
    X = offers[feats]
    mdl = XGBRegressor(n_estimators=300,max_depth=6,learning_rate=0.1,subsample=0.8,
                       colsample_bytree=0.8,random_state=42,n_jobs=-1).fit(X.iloc[tri], y.iloc[tri])
    print(feats, MAPE(np.exp(y.iloc[vai]), np.exp(mdl.predict(X.iloc[vai]))))
```
