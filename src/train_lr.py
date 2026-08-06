"""
Linear regression baseline for the flight price predictor.

The point of this script isn't the model — it's the first end-to-end run that
exercises split → features → fit → eval. LR gives XGBoost a number to beat;
if XGBoost can't outperform a linear baseline, something's wrong with the
features or the split.

Pipeline:
    raw offers → split_offers_grouped() → build_features() (FIT on train, APPLY to val/test)
              → prepare_xy()    → LinearRegression.fit() → MAPE on dollars
"""
import sqlite3
import time

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error

from src.split import split_offers_grouped
from src.features import build_features, prepare_xy  # prepare_xy re-exported for train_xgb
from src.metrics import bootstrap_mape_ci
from src.config import SNAPSHOT_DATE


def load_raw(snapshot=SNAPSHOT_DATE):
    """
    Open data/flights.db and read offers, airports, airlines into DataFrames.
    `offers` is capped to captures on or before `snapshot`. The default is the
    frozen SNAPSHOT_DATE (src/config.py) so experiment runs stay comparable;
    deploy builds (src/build_deploy_model.py) pass today's date instead to
    train on everything collected so far.
    Return (offers, airports, airlines).
    """
    # Read-only + retry: the daily collector can hold the write lock for hours
    # (documented in documentation/live_data_logging.md). A plain connect()
    # fails with "database is locked" while it runs; training only reads.
    for attempt in range(6):
        try:
            conn = sqlite3.connect("file:data/flights.db?mode=ro", uri=True, timeout=30)
            break
        except sqlite3.OperationalError:
            if attempt == 5:
                raise
            time.sleep(5)
    offers = pd.read_sql(
        "SELECT * FROM offers WHERE substr(captured_at, 1, 10) <= ?",
        conn, params=[snapshot],
    )
    airports = pd.read_sql("SELECT * FROM airports", conn)
    airlines = pd.read_sql("SELECT * FROM airlines", conn)
    return offers, airports, airlines



# prepare_xy moved to src/features.py (2026-08-05) so the serving path and both
# trainers share one implementation — same reason train_xgb imports from here
# instead of copying: one source of truth, no silent drift. Import above keeps
# `from src.train_lr import prepare_xy` working.


def evaluate(model, X, y_log):
    """
    Predict, inverse the log transform, return MAPE on dollar space.
    Caller is responsible for labeling/printing.
    """
    log_pred = model.predict(X)

    # Inverse the log transform so MAPE is in dollars, not log-dollars.
    dollar_pred = np.exp(log_pred)
    dollar_true = np.exp(y_log)

    return mean_absolute_percentage_error(dollar_true, dollar_pred)


def main():
    offers, airports, airlines = load_raw()

    # 1. Split RAW offers (BEFORE feature engineering) — date-grouped regime:
    #    random deal of whole trips into train/val; test stays chronological.
    train_offers, val_offers, test_offers = split_offers_grouped(offers)
    print(f"rows: train={len(train_offers)}, val={len(val_offers)}, test={len(test_offers)}")

    # 2. Build features — FIT route_means on train, APPLY to val/test
    train_df, route_means = build_features(train_offers, airports, airlines, route_means=None)
    val_df,   _ = build_features(val_offers,   airports, airlines, route_means=route_means)
    test_df,  _ = build_features(test_offers,  airports, airlines, route_means=route_means)

    # 3. Convert to (X, y). Capture train's column set so val/test align.
    X_train, y_train, train_cols = prepare_xy(train_df, train_columns=None)
    X_val,   y_val,   _          = prepare_xy(val_df,   train_columns=train_cols)
    # test held out — don't touch until stopped tuning

    # 4. Fit
    model = LinearRegression()
    model.fit(X_train, y_train)

    # 5. Evaluate on train + val only
    train_mape = evaluate(model, X_train, y_train)
    val_mape   = evaluate(model, X_val,   y_val)

    # 6. Error bar on the val score: itinerary-clustered bootstrap CI.
    #    Same inverse-log transform as evaluate(); rows of X_val line up 1:1
    #    with val_df, so val_df["itinerary_id"] labels the predictions.
    dollar_pred = np.exp(model.predict(X_val))
    dollar_true = np.exp(y_val)
    ci_low, ci_high = bootstrap_mape_ci(dollar_true, dollar_pred, val_df["itinerary_id"])

    print(f"\ntrain MAPE: {train_mape:.3f}")
    print(f"val MAPE:   {val_mape:.3f}  (95% CI: {ci_low:.3f} – {ci_high:.3f})")


if __name__ == "__main__":
    main()
