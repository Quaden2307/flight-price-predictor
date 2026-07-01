# Modeling runs — frozen-split regime

> **Fresh sheet started 2026-06-30.** Runs #1–6 (pre-freeze, drifting quantile split, pre-deep-dive) are archived in [`archive/modeling_runs_prefreeze_2026-06-30.md`](archive/modeling_runs_prefreeze_2026-06-30.md) — kept for history, **not comparable** to runs here. Numbering continues from the archive (this sheet starts at #7) so every run keeps a unique id.
>
> One row per run; **change one variable per run.**

## Reading a number — the regime decides everything
The same model scores very differently depending on the split. **Never compare across regimes:**
- **chronological-by-departure** ≈ 0.16 — a lead-time-extrapolation *artifact* on young data. Not a skill measure; don't optimize it.
- **date-grouped** (GroupShuffleSplit on `origin+destination+departure_at`) ≈ 0.133 — **the honest pass/fail gate.**
- **flight-grouped** ≈ 0.119 — in-distribution ceiling (report as context only).

**Judge on date-grouped + an itinerary-clustered bootstrap CI.** Effective N ≈ 4,500 itineraries (not row count) → CI ≈ ±0.005 → **deltas < 0.006 are ties.**

**Tier-A vs Tier-B:** deployment sees only query-time inputs (route + dates). `airline`, `airline_type`, `transfers` are **Tier-B** offer outcomes — they inflate scores ~1–3pp but aren't available at inference. Judge deployability on **Tier-A only.**

## Goals (honest, post-deep-dive)
- **Near-term gate:** date-grouped, Tier-A, itinerary-clustered-CI val MAPE **< 0.12**.
- **Stretch / product promise:** **median APE < 0.10** in the 2–5-month booking window (already roughly holds).
- A *global-mean* MAPE < 0.10 sits **below the ~0.145 data floor** → not honestly reachable. See memory `eval-regime-and-012-verdict` and `horizon_error_profile_2026-06-03.md`.

## Conventions
- Commit = short SHA (`git rev-parse --short HEAD`); dirty tree → `abc1234 +dirty`.
- Always log the **split/regime** and the **CI**, not just a point estimate.
- MAPE = fraction (0.167 means 16.7%).
- Test column stays blank until the FINAL run on the chosen tuned model (section at bottom).

## Runs

| # | Date | Commit | Split / regime | Rows (tr/val) | Features (tier) | Model | Train | Val | Val CI | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| 7 | 2026-06-30 | 95363c1 | chronological, **FROZEN** (cutoffs Aug 6 / Sep 12; snapshot 2026-06-28) | 162241/34972 | baseline-v1 (Tier-A+B) | LR (defaults) | 0.169 | 0.167 | — | **Re-baseline on the frozen split** (freeze in `config.py` / `split.py` / `train_lr.py`). ≈ unchanged from the pre-freeze 0.166 → the freeze stabilized the split **without distorting** it. train ≈ val → no overfit, LR generalizes cleanly. NOTE: still the *chronological + Tier-B* anchor; the honest date-grouped number arrives in the next runs. |

## Up next (the plan — one variable per run)
- [x] **#7 — freeze split + re-baseline** (this run).
- [ ] **#8 — itinerary-clustered bootstrap CI** in `evaluate()` → establishes the ±0.005 band / 0.006 tie threshold.
- [ ] **#9 — date-grouped split**, adopt as the model-selection regime (report flight-grouped as the ceiling).
- [ ] **#10 — Tier-A-only run** on the date-grouped gate → the decisive deployable number (expect ~0.14–0.16).
- *Later:* OOF + thin-route-smoothed route encoding · sin/cos month · CatBoost / native-cat XGB · MdAPE + log-RMSE + horizon bands · prediction intervals + cold-start confidence flag.

## Feature sets

### baseline-v1 (active)
- Numeric: `distance_km`, `lead_time_days`, `transfers`, `is_international`, `route_mean_log_price`
- Dummified: `airline`, `airline_type`, `day_of_week`, `month_of_year`
- Target: `log_price` (i.e. `np.log(price)`)
- ⚠ **Tier mix:** `airline`, `airline_type`, `transfers` are Tier-B (offer outcomes). The Tier-A/Tier-B column contract lands at run #10.

> The old **baseline-v2** rationale (per-leg durations, `return_transfers`, etc.) lives in the archive. The deep dive reframed most of it as **Tier-B or tie-level** on the honest regime — re-evaluate each against the Tier-A contract before adopting, rather than taking the pre-freeze correlations at face value.

## Final test evaluation

Touched once at the very end, on the chosen tuned model.

| Run # | Test MAPE | Date | Notes |
|---|---|---|---|
