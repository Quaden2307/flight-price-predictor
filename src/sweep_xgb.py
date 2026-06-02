"""
XGBoost regularization sweep (run #3).

Run #2 showed vanilla XGBoost overfits hard (train 0.059 / val 0.269, gap 0.210)
and didn't beat the LR baseline (val 0.257). This sweep grid-searches the main
regularization levers to answer two things:
    1. Can a regularized XGBoost get under the 0.257 bar?
    2. WHICH knob actually moves the train/val gap — i.e. where to dig next.

Same pipeline as train_lr.py / train_xgb.py (shared helpers imported from
train_lr), so the config is the only thing that varies across the sweep.

`val` is a READ-ONLY holdout: we never fit or early-stop on it. We grid only
over train-side model knobs and report val MAPE per config. Reading the table
to pick a direction is fine for exploration; the final tuned model gets
confirmed on the untouched TEST set later.

Side effect: writes every config + metric to RESULTS_CSV for plotting.
"""
import itertools
import time
import csv

from xgboost import XGBRegressor

from src.split import split_offers
from src.features import build_features
from src.train_lr import load_raw, prepare_xy, evaluate

RESULTS_CSV = "documentation/run3_xgb_sweep.csv"
BASELINE_VAL = 0.257  # LR run #1 — the number to beat
RUN2_VAL = 0.269      # vanilla XGB run #2 — for reference

# Grid over the highest-impact regularization levers. The combo
# depth=6 / mcw=1 / lambda=1 reproduces run #2 (val ~0.269) as an anchor.
GRID = {
    "max_depth":        [3, 4, 6],
    "min_child_weight": [1, 5, 20],
    "reg_lambda":       [1, 10],
}

# Held constant across the sweep so the grid isolates regularization.
FIXED = dict(
    n_estimators=300,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
)


def main():
    overall_start = time.perf_counter()

    # --- shared pipeline (identical to train_lr / train_xgb) ---
    offers, airports, airlines = load_raw()
    train_offers, val_offers, _ = split_offers(offers)
    train_df, route_means = build_features(train_offers, airports, airlines, route_means=None)
    val_df, _ = build_features(val_offers, airports, airlines, route_means=route_means)
    X_train, y_train, train_cols = prepare_xy(train_df, train_columns=None)
    X_val, y_val, _ = prepare_xy(val_df, train_columns=train_cols)
    print(f"data ready: train={len(X_train)} val={len(X_val)}  "
          f"(baseline LR val={BASELINE_VAL}, vanilla XGB run#2 val={RUN2_VAL})\n")

    # --- sweep ---
    keys = list(GRID.keys())
    combos = list(itertools.product(*(GRID[k] for k in keys)))
    rows = []
    for values in combos:
        params = dict(zip(keys, values))
        model = XGBRegressor(**params, **FIXED)
        model.fit(X_train, y_train)
        tr = evaluate(model, X_train, y_train)
        va = evaluate(model, X_val, y_val)
        rows.append({
            **params,
            "train_mape": round(tr, 4),
            "val_mape": round(va, 4),
            "gap": round(va - tr, 4),
            "beats_baseline": va < BASELINE_VAL,
        })

    # --- results table, sorted best (lowest val) first ---
    rows.sort(key=lambda r: r["val_mape"])
    print(f"{'depth':>5} {'mcw':>4} {'lambda':>6} | {'train':>6} {'val':>6} {'gap':>6} | vs base")
    print("-" * 56)
    for r in rows:
        flag = f"BEATS by {BASELINE_VAL - r['val_mape']:+.3f}" if r["beats_baseline"] \
               else f"{r['val_mape'] - BASELINE_VAL:+.3f}"
        print(f"{r['max_depth']:>5} {r['min_child_weight']:>4} {r['reg_lambda']:>6} | "
              f"{r['train_mape']:>6.3f} {r['val_mape']:>6.3f} {r['gap']:>6.3f} | {flag}")

    # --- write CSV for plotting ---
    with open(RESULTS_CSV, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    best = rows[0]
    n_beat = sum(r["beats_baseline"] for r in rows)
    print(f"\nbest val: {best['val_mape']:.3f} at "
          f"depth={best['max_depth']} mcw={best['min_child_weight']} lambda={best['reg_lambda']} "
          f"(gap {best['gap']:.3f})")
    print(f"{n_beat}/{len(rows)} configs beat the {BASELINE_VAL} baseline")
    print(f"wrote {RESULTS_CSV}")
    print(f"\ntotal {time.perf_counter() - overall_start:.2f}s")


if __name__ == "__main__":
    main()
