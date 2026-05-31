"""
XGBoost run for the flight price predictor (run #2).

Deliberately the same pipeline as the LR baseline (src/train_lr.py) — identical
split, features, (X, y) prep, and dollar-space MAPE eval — so the ONLY thing
that changes is the model. That isolates the question this run exists to answer:
what does a gradient-boosted tree buy us over linear regression?

Number to beat: the LR baseline at val MAPE 0.257 (run #1).

The shared pipeline pieces (load_raw / prepare_xy / evaluate) are imported from
src.train_lr rather than copied, so the two runs can't silently drift apart and
there's one source of truth for "the pipeline."
"""
import time

from xgboost import XGBRegressor

from src.split import split_offers
from src.features import build_features
from src.train_lr import load_raw, prepare_xy, evaluate


def main():
    overall_start = time.perf_counter()

    t = time.perf_counter()
    offers, airports, airlines = load_raw()
    print(f"[1/6] load_raw         {time.perf_counter() - t:6.2f}s")

    # 1. Same chronological split as the baseline (by departure_at).
    t = time.perf_counter()
    train_offers, val_offers, test_offers = split_offers(offers)
    print(f"[2/6] split_offers     {time.perf_counter() - t:6.2f}s")

    # 2. Same features — FIT route_means on train, APPLY to val. Test held out.
    t = time.perf_counter()
    train_df, route_means = build_features(train_offers, airports, airlines, route_means=None)
    val_df,   _ = build_features(val_offers,   airports, airlines, route_means=route_means)
    print(f"[3/6] build_features   {time.perf_counter() - t:6.2f}s")

    # 3. Same (X, y) prep — identical one-hot feature matrix as LR, so the
    #    comparison isolates the model and nothing else.
    t = time.perf_counter()
    X_train, y_train, train_cols = prepare_xy(train_df, train_columns=None)
    X_val,   y_val,   _          = prepare_xy(val_df,   train_columns=train_cols)
    print(f"[4/6] prepare_xy       {time.perf_counter() - t:6.2f}s")

    # 4. Fit. No early stopping on val — keep val a clean holdout, exactly like
    #    the LR baseline (no peeking). Hyperparameters are intentionally vanilla
    #    for a first XGBoost run; tuning is a later run once we know the lift.
    t = time.perf_counter()
    model = XGBRegressor(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        n_jobs=-1,
    )
    model.fit(X_train, y_train)
    print(f"[5/6] fit (XGB)        {time.perf_counter() - t:6.2f}s")

    # 5. Evaluate on train + val only (dollar-space MAPE, same as baseline).
    t = time.perf_counter()
    train_mape = evaluate(model, X_train, y_train)
    val_mape   = evaluate(model, X_val,   y_val)
    print(f"[6/6] evaluate         {time.perf_counter() - t:6.2f}s")

    print(f"\ntrain MAPE: {train_mape:.3f}")
    print(f"val MAPE:   {val_mape:.3f}")
    print(f"(baseline to beat: val 0.257)")

    print(f"\ntotal                  {time.perf_counter() - overall_start:6.2f}s")


if __name__ == "__main__":
    main()
