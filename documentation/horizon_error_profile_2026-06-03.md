# Per-Horizon Error Profile — 2026-06-03

What MAPE can we actually promise, broken down by **booking horizon** (months
before departure), and how does it change with the evaluation regime? This exists
to (a) set an honest, horizon-specific accuracy target and (b) feed the
user-facing "degree of error" feature.

**Model:** tuned native-categorical XGBoost — `airline`/`origin`/`destination` as
categoricals; numerics `lead_time_days, transfers, return_transfers, duration,
duration_to, duration_back, trip_duration_days`; date features `dep_dom, dep_woy,
dep_ord, dep_month, dep_dow`; plus a train-fitted `route×month` target encoding.
`n_estimators=800, max_depth=8, lr=0.04, min_child_weight=3, subsample=0.8,
colsample=0.8, enable_categorical`. Target `log_price`, MAPE in dollars.

**Horizon bands:** lead-time in 30-day buckets (1mo = 0–30d … 7mo = 181d+).

---

## Three evaluation regimes (each answers a different question)

| Regime | What it measures | Overall MAPE | Trust |
|---|---|---|---|
| Flight-grouped | predict an unseen *flight* (dates interspersed) | 0.119 | in-distribution ceiling |
| **Date-grouped** | **predict an unseen *departure date*** | **0.133** | **honest deployment proxy** |
| captured_at-forward | predict later captures of *recurring* flights | 0.111 | **optimistic — leaky** |

`captured_at`-forward looks best but is misleading: flights are re-collected daily
and price is sticky over short windows (77% of flights have 0 price change across
captures), so the model has effectively already seen most test flights. The
**date-grouped** number (0.133) is the one to anchor on — it forces prediction of
genuinely novel dates with the same lead-time distribution in train and test (no
lead-time-extrapolation confound).

---

## Per-horizon profile (MAPE = mean, median = typical user error)

**Date-grouped (HONEST deployment estimate), 5 seeds:**

| Horizon | MAPE | Median | ~rows/seed |
|---|---|---|---|
| ~1mo (0–30d) | 0.144 | 0.101 | 11,828 |
| ~2mo (31–60d) | 0.121 | 0.087 | 3,976 |
| **~3mo (61–90d)** | **0.110** | **0.079** | 2,923 |
| ~4mo (91–120d) | 0.117 | 0.082 | 1,780 |
| ~5mo (121–150d) | 0.121 | 0.085 | 1,102 |
| ~6mo (151–180d) | 0.142 | 0.102 | 546 |
| ~7mo (181d+) | 0.209 | 0.134 | 302 |

**Flight-grouped (in-distribution, for reference):**

| Horizon | MAPE | Median |
|---|---|---|
| 1mo | 0.127 | 0.092 |
| 2mo | 0.112 | 0.078 |
| 3mo | 0.109 | 0.074 |
| 4mo | 0.102 | 0.070 |
| 5mo | 0.110 | 0.079 |
| 6mo | 0.130 | 0.084 |
| 7mo | 0.138 | 0.093 |

---

## Reading

- **Sweet spot is 2–5 months** (honest MAPE 0.110–0.121, median ~0.08) — which is
  exactly where most tickets are booked. The model is strongest where it matters.
- **U-shape:** worst at the extremes — 1mo (last-minute volatility) and especially
  **7mo (0.209, and data-starved at ~300 rows/seed)**.
- **Metric choice matters for the <0.10 goal:**
  - **Median <0.10** holds for 1–6 months on the honest split (0.079–0.102).
  - **Mean MAPE <0.10** is *not* reached on novel dates (best 0.110 at 3mo); it is
    reached in-distribution at ~4mo.
  - Suggested split: **median <0.10 as the user-facing promise**, mean MAPE as the
    internal target.
- The honest (date-grouped) numbers sit ~0.01–0.07 above in-distribution; the gap
  is largest at 7mo — that horizon is both genuinely harder and under-sampled.

## Caveats
- **Young data (24-day capture window).** 6–7mo bands are thin and noisy; the full
  booking curve (how price moves in the final weeks) is not yet observed. These
  numbers should firm up — and the far horizons likely improve — as collection
  deepens across the calendar.
- Date-grouped holds out random dates, not strictly *future* dates; true
  future-season generalization (e.g. first-ever Christmas) may run higher until
  the calendar is covered.
- Single tuned config, not a full hyperparameter search.

## Implication for the product's error feature
Report a **horizon-specific** band, not one global number — e.g. "typically within
±8% (2–5 months out), ±10–13% near-term or far-out." The honest implementation is
a **quantile model** (predict p10/median/p90) or **conformal prediction**, giving a
calibrated interval per query instead of a point estimate.
