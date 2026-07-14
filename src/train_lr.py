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

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error

from src.split import split_offers_grouped
from src.features import build_features
from src.metrics import bootstrap_mape_ci
from src.config import SNAPSHOT_DATE


def load_raw():
    """
    Open data/flights.db and read offers, airports, airlines into DataFrames.
    `offers` is frozen to the SNAPSHOT_DATE capture window (see src/config.py).
    Return (offers, airports, airlines).
    """
    conn = sqlite3.connect("data/flights.db")
    # Snapshot freeze: only offers captured on or before SNAPSHOT_DATE, so the
    # training set doesn't grow between runs. Reference tables aren't time-keyed.
    offers = pd.read_sql(
        "SELECT * FROM offers WHERE substr(captured_at, 1, 10) <= ?",
        conn, params=[SNAPSHOT_DATE],
    )
    airports = pd.read_sql("SELECT * FROM airports", conn)
    airlines = pd.read_sql("SELECT * FROM airlines", conn)
    return offers, airports, airlines
    


def prepare_xy(df, train_columns=None):
    """
    Split modeling DataFrame into (X, y) and make X numeric for LR.

    Parameters
    ----------
    df : pd.DataFrame
        Output of build_features — has log_price + feature columns.
    train_columns : pd.Index or None
        On train: pass None, function returns the dummified column set.
        On val/test: pass train's columns so the shapes line up.

    Returns
    -------
    (X, y, columns)
        X : numeric DataFrame ready for LinearRegression
        y : log_price Series
        columns : the column set used (return so val/test can reuse it)
    """
    # 1. Separate target from features. log_price is what we're predicting,
    #    so it can't be in X — that'd be target leakage (trivial perfect fit).
    #    itinerary_id is a grouping label for the bootstrap CI, not a feature,
    #    so it goes too (before get_dummies, or it'd explode into ~6k columns).
    y = df["log_price"]
    X = df.drop(columns=["log_price", "itinerary_id", "airline", "airline_type", "transfers"])

    # 2. Dummify string/categorical columns so LR can consume them.
    # Alt encoding for month_of_year (option B): sin/cos pair instead of dummies.
    #   X["month_sin"] = np.sin(2*np.pi * X["month_of_year"] / 12)
    #   X["month_cos"] = np.cos(2*np.pi * X["month_of_year"] / 12)
    # Dummies treat Dec and Jan as unrelated buckets; sin/cos preserves adjacency.
    # Useful when the chronological split leaves some months only in test —
    # sin/cos interpolates while dummies just zero out. Baseline uses dummies;
    # revisit if test-set months mostly fall outside train coverage.
    X = pd.get_dummies(X, columns=["day_of_week", "month_of_year"])

    # 3. On val/test, force X to match train's column set (same names, same order).
    #    Missing columns -> filled with 0. New columns in val/test -> dropped.
    #    On train (train_columns=None), skip this — X.columns IS the source of truth.
    if train_columns is not None:
        X = X.reindex(columns=train_columns, fill_value=0)

    return X, y, X.columns



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
