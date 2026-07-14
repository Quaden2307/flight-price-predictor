"""
XGBoost run for the flight price predictor (run #11).

Deliberately the same pipeline as the LR baseline (src/train_lr.py) — identical
split, features, (X, y) prep, dollar-space MAPE, and itinerary-clustered CI —
so the ONLY thing that changes is the model. That isolates the question this
run exists to answer: what does a gradient-boosted tree buy us over LR?

Number to beat: the deployable baseline at val MAPE 0.171 (run #10 — LR,
Tier-A features, date-grouped gate, CI 0.166–0.175).

The shared pipeline pieces (load_raw / prepare_xy / evaluate) are imported from
src.train_lr rather than copied, so the two runs can't silently drift apart and
there's one source of truth for "the pipeline."
"""
import numpy as np
from xgboost import XGBRegressor

from src.split import split_offers_grouped
from src.features import build_features
from src.metrics import bootstrap_mape_ci
from src.train_lr import load_raw, prepare_xy, evaluate


def main():
    offers, airports, airlines = load_raw()

    # 1. Same date-grouped split as run #10: whole trips dealt randomly to
    #    train/val; test untouched (chronological, departures ≥ Sep 12).
    train_offers, val_offers, test_offers = split_offers_grouped(offers)
    print(f"rows: train={len(train_offers)}, val={len(val_offers)}, test={len(test_offers)}")

    # 2. Same features — FIT route_means on train, APPLY to val. Test held out.
    train_df, route_means = build_features(train_offers, airports, airlines, route_means=None)
    val_df,   _ = build_features(val_offers,   airports, airlines, route_means=route_means)

    # 3. Same (X, y) prep — identical one-hot feature matrix as LR, so the
    #    comparison isolates the model and nothing else.
    X_train, y_train, train_cols = prepare_xy(train_df, train_columns=None)
    X_val,   y_val,   _          = prepare_xy(val_df,   train_columns=train_cols)

    # 4. Fit. No early stopping on val — keep val a clean holdout, exactly like
    #    the LR baseline (no peeking). Hyperparameters are intentionally vanilla
    #    for a first XGBoost run; tuning is a later run once we know the lift.
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

    # 5. Evaluate on train + val only (dollar-space MAPE, same as baseline).
    train_mape = evaluate(model, X_train, y_train)
    val_mape   = evaluate(model, X_val,   y_val)

    # 6. Error bar on the val score — same itinerary-clustered bootstrap as LR.
    dollar_pred = np.exp(model.predict(X_val))
    dollar_true = np.exp(y_val)
    ci_low, ci_high = bootstrap_mape_ci(dollar_true, dollar_pred, val_df["itinerary_id"])

    print(f"\ntrain MAPE: {train_mape:.3f}")
    print(f"val MAPE:   {val_mape:.3f}  (95% CI: {ci_low:.3f} – {ci_high:.3f})")
    print(f"(baseline to beat: val 0.171)")


if __name__ == "__main__":
    main()
