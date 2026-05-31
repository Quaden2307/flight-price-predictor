# Modeling runs

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

## Feature sets

### baseline-v1
- Numeric: `distance_km`, `lead_time_days`, `transfers`, `is_international`, `route_mean_log_price`
- Dummified: `airline`, `airline_type`, `day_of_week`, `month_of_year`
- Target: `log_price` (i.e. `np.log(price)`)

## Final test evaluation

Touched once at the very end, on the chosen tuned model.

| Run # | Test MAPE | Date | Notes |
|---|---|---|---|
