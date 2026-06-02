# Modeling runs

> **Target:** val MAPE < 0.12 by 2026-08-01. Stretch goal for the deployable model.
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

## Feature sets

### baseline-v1
- Numeric: `distance_km`, `lead_time_days`, `transfers`, `is_international`, `route_mean_log_price`
- Dummified: `airline`, `airline_type`, `day_of_week`, `month_of_year`
- Target: `log_price` (i.e. `np.log(price)`)

## Final test evaluation

Touched once at the very end, on the chosen tuned model.

| Run # | Test MAPE | Date | Notes |
|---|---|---|---|
