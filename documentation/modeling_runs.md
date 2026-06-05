# Modeling runs

> **Target:** val MAPE < 0.10 by 2026-08-01 (tightened from 0.12 on 2026-06-01). Stretch goal for the deployable model.
> **Caveat:** "val MAPE" must specify an evaluation regime — see `audit_review_opus-4-8.md`. <0.10 looks reachable in-distribution (grouped/CV: native-cat XGB already ~0.122) but is NOT currently attainable on the temporal/long-lead split (~0.16 plateau, confounded by young data). Pick the regime before treating 0.10 as pass/fail.
> **Per-horizon error profile (2026-06-03):** see `horizon_error_profile_2026-06-03.md`. Honest (date-grouped, novel-date) MAPE by booking horizon: ~1mo 0.144, 2–5mo 0.110–0.121 (median ~0.08), 6mo 0.142, 7mo 0.209 (sparse). Median <0.10 holds 1–6 months; mean MAPE <0.10 not yet reached on novel dates. Sweet spot 2–5 months matches real booking behavior.
>
> One row per training run. Goal: never lose track of what changed between runs.
>
> **Conventions:**
> - Commit = short SHA (`git rev-parse --short HEAD`). If the working tree is dirty, write `abc1234 +dirty` and note the delta in Notes.
> - Features = compact identifier; full column list in the "Feature sets" section below.
> - MAPE values are fractions, not percentages (0.180 means 18% mean abs % error).
> - Test column stays blank until the FINAL run on the chosen tuned model — see separate section at the bottom.

## Runs

| # | Date | Commit | Rows (tr/val) | Features | Model | Train MAPE | Val MAPE | Notes |
|---|---|---|---|---|---|---|---|---|
| 1 | 2026-05-30 | c815c8b | 63158/13544 | baseline-v1 | LR (defaults) | 0.192 | 0.257 | First end-to-end run. Mild overfit (gap 0.065). Features carry real signal — val survives chronological jump from train period to later months. Bar for XGBoost: <0.257. |
| 2 | 2026-05-31 | d9b432b +dirty | ~6k/1k (split 65655/14098)† | baseline-v1 | XGB (n300/d6/lr.1/ss.8/cs.8) | 0.059 | 0.269 | Vanilla XGBoost via `src/train_xgb.py` (reuses split/features/prepare_xy from train.py — model is the only change). Did NOT beat baseline: val 0.269 > 0.257, despite near-perfect train fit (0.059). Severe overfit — gap 0.210 vs LR's 0.065. Memorizing the train period, not generalizing across the chronological jump. Confound: +3588 rows vs run #1 (today's collection grew the db), so not a pure model-only delta, but the overfit gap dwarfs that. Next: **regularize** (shallower depth, min_child_weight, reg_lambda, lower lr), not more trees. `+dirty` = added train_xgb.py + venv recreate / requirements.txt / path fixes; no pipeline logic changed. **† Correction (found in run #3):** 65655/14098 was the pre-feature *split* size; `build_features` drops ~91% of rows on NaN `distance_km`, so the model actually trained on ~6k/1k. |
| 3 | 2026-06-01 | f7133c9 | 6062/1002 (split 68315/~15.2k) | baseline-v1 | XGB sweep — 18 cfg: depth{3,4,6}×mcw{1,5,20}×λ{1,10}, fixed n300/lr.1/ss.8/cs.8 | 0.136 (best) | **0.247 (best)** | Regularization sweep via `src/sweep_xgb.py` (val kept read-only; CSV → `documentation/run3_xgb_sweep.csv`). Best val **0.247** at depth=3/mcw=20/λ=1 (gap 0.112); 7/18 configs beat the 0.257 bar. Clear trend: shallow depth + high min_child_weight crush the overfit gap (0.203→0.112). But XGB only edges LR by ~0.01 — the tell that **both models are data-starved**. **HEADLINE FINDING:** every run so far trains on only ~9% of collected offers — [features.py:108](../src/features.py#L108) `dropna` deletes 91% of rows on NaN `distance_km`, because the `airports` table (55 codes) lacks the metro/city IATA codes the collector requests (NYC, TYO, LON, SEL, CHI, PAR, ROM, SAO, BJS, SHA…). **Next research direction = fix coordinate coverage (map city codes → coords / expand airports table), NOT more tuning.** Re-run #1–3 after the fix; current MAPEs are on a biased ~6k-row subset. |

> **⎯⎯ Airport-coverage fix applied (2026-06-01, commit 408d912) ⎯⎯**
> `populate_airports.py` now loads the metro/city codes the API returns → `airports` table 55 → 76 codes → coordinate coverage 8.3% → 100%. Training matrix jumps ~6k → **68k rows (11×)**. Runs #1–3 above are on the pre-fix biased subset and are kept for history only; runs #4+ are on the full data and are the real numbers.

| 4 | 2026-06-01 | 408d912 +dirty | 68315/14635 | baseline-v1 | LR (defaults) | 0.175 | **0.166** | First run **after the coverage fix** — full 68k data. Val MAPE **0.257 → 0.166** purely from recovering the lost rows; the data, not the model, was the lever. Notably val (0.166) < train (0.175): LR no longer overfits — with 11× data the `route_mean_log_price` feature generalizes cleanly across the chronological jump. **New bar for XGBoost: <0.166** (updated in train_xgb.py / sweep_xgb.py). Target val<0.12 by Aug 1 now looks reachable. |
| 5 | 2026-06-01 | 408d912 +dirty | 68315/14635 | baseline-v1 | XGB (n300/d6/lr.1/ss.8/cs.8) | 0.117 | 0.181 | Vanilla XGBoost on full data. Does **not** beat LR: val 0.181 > 0.166. Small residual overfit (gap 0.064) vs LR's none. |
| 6 | 2026-06-01 | 408d912 +dirty | 68315/14635 | baseline-v1 | XGB sweep — 18 cfg: depth{3,4,6}×mcw{1,5,20}×λ{1,10}, fixed n300/lr.1/ss.8/cs.8 | 0.122 (best) | **0.178 (best)** | Regularization sweep on full data (CSV → `documentation/run3_xgb_sweep.csv`). **0/18 configs beat the 0.166 LR bar**; best val 0.178 at depth=6/mcw=5/λ=10. Trend reversed vs run #3: deeper trees now win. ~~CONCLUSION: the signal is essentially linear~~ — **RETRACTED, see findings block below.** |

> **⎯⎯ ⚠ Deep audit (2026-06-01): the LR>XGB verdict was a SPLIT ARTIFACT, not a real result ⎯⎯**
> The chronological-by-`departure_at` split, on this *young* dataset, confounds departure date with lead time: **train lead_time 0–72d, val 50–113d, test 91–213d** — barely overlapping. Trees can't extrapolate to unseen lead-time ranges; LR's linear fit can. So the split structurally punished XGB and flattered LR.
> **Leak-free grouped-random split (flights kept together, no lead-time shift): LR 0.180 vs XGB 0.141 — XGB *wins* by 0.039.** The "signal is linear" conclusion from runs #4–6 is withdrawn.
> **Bigger finding — three of the most predictive columns are UNUSED:** `corr(log_price, duration)=+0.724`, `return_transfers=+0.49`, `trip_duration_days=+0.30` (data is *round-trip*!). XGB on just 7 raw itinerary numbers (no route/airline/route_mean) already hits **0.173**. Adding `duration` alone moves 0.402→0.173.
> **Revised plan:** (1) fix the validation design (grouped-random for model selection; chronological confound is a young-data artifact that self-heals as collection continues); (2) build `baseline-v2` with duration / return_transfers / trip_duration_days (+ origin_airport/destination_airport — real airport codes already in the data); (3) *then* compare LR vs XGB (native categoricals) — XGB expected to win and approach the 0.12 target. **Scoping decision (2026-06-01): TIERED — itinerary-level model is the active track (all itinerary features valid: duration, transfers, return_transfers, trip_duration_days); a route+date model is parked as a separate future track.** |

## Feature sets

### baseline-v1
- Numeric: `distance_km`, `lead_time_days`, `transfers`, `is_international`, `route_mean_log_price`
- Dummified: `airline`, `airline_type`, `day_of_week`, `month_of_year`
- Target: `log_price` (i.e. `np.log(price)`)

### baseline-v2 (proposed 2026-06-04)
Adds the round-trip itinerary features v1 left on the table. The core realization: **v1 modeled a round-trip as if it were one-way** — only outbound `transfers`, no leg durations, no trip length.

- Numeric: baseline-v1 + `duration_to`, `duration_back`, `return_transfers`, `trip_duration_days`
- Dummified: same as v1 (`airline`, `airline_type`, `day_of_week`, `month_of_year`)
- Target: `log_price`
- Deliberately **NOT** included: total `duration` — per-leg times are cleaner (see Surprise 1).

**Rationale (data as of 110,507 rows, 2026-06-04):**
- All candidate columns already exist in `offers` with **0 nulls** — no computation/cleaning needed.
- `corr(log_price, X)`: `distance_km` **+0.853** | `duration_back` +0.831 | `duration_to` +0.819 | `duration` +0.727 | `transfers` +0.495 | `return_transfers` +0.495 | `trip_duration_days` +0.299 | `lead_time_days` +0.122.
- **Surprise 1 — per-leg durations beat total `duration`.** `duration` is NOT the sum of the legs (median 935 vs 644 min; equal only 41% of rows), so it folds in **layover/connection time**, which is noise w.r.t. price (long layovers often mean *cheaper* budget routings — they pull opposite to airtime). `duration_to`/`duration_back` are cleaner airtime and correlate better. → use the per-leg pair, not total.
- **Surprise 2 — round-trip asymmetry.** `return_transfers` (+0.495) is as predictive as `transfers` (+0.495), but v1 used only the outbound leg; same for leg durations. v1 silently threw away the return half of a round-trip product.
- **Why `duration` was omitted from v1:** `corr(duration, distance_km) = +0.795` — ~80% collinear with distance, which v1 already had, so it read as redundant (and v1 was a deliberate minimal first pass). But correlated ≠ redundant: duration carries routing/layover signal distance misses (audit: adding duration moved 0.402→0.173). Collinearity destabilizes *linear* coefficients (a legitimate reason the LR-based v1 dropped it) but is harmless for **trees** — so v2 + XGBoost can use distance and durations together.
- **Independence from distance (partial corr | `distance_km`, 2026-06-04):** distance alone already explains **R²=0.728** of log-price. Most of the durations' giant raw correlations ARE distance in disguise: `duration_to` collapses +0.819→**+0.082**, `duration` +0.727→+0.154, `duration_back` +0.831→**+0.182**. Transfers are *less* distance-collinear and hold up best: `return_transfers` +0.495→**+0.181**, `transfers` +0.495→+0.173. `trip_duration_days` signal **vanishes** (+0.299→−0.017, ΔR² 0.000) — pure distance confound, **drop it**. `lead_time_days` **flips sign** (+0.122→**−0.153**): controlling for distance reveals the real within-distance effect is *negative* (book earlier → cheaper); the raw positive was a long-haul-books-earlier artifact.
  - **Caveat:** these are LINEAR measures (single-feature incremental R² ≤ +0.009 each), so they understate value for a tree — XGBoost can still mine nonlinear/interaction signal they can't see. Tempers priors; not grounds to pre-drop features *for the tree* — except `trip_duration_days`, which is a clean drop.
  - **Refined v2 priority:** `return_transfers` + `duration_back` carry the most distance-independent signal; `duration_to`/total `duration` are mostly redundant with distance; `trip_duration_days` out.

## Final test evaluation

Touched once at the very end, on the chosen tuned model.

| Run # | Test MAPE | Date | Notes |
|---|---|---|---|
