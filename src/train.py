"""
Linear regression baseline for the flight price predictor.

The point of this script isn't the model — it's the first end-to-end run that
exercises split → features → fit → eval. LR gives XGBoost a number to beat;
if XGBoost can't outperform a linear baseline, something's wrong with the
features or the split.

Pipeline:
    raw offers → split_offers() → build_features() (FIT on train, APPLY to val/test)
              → prepare_xy()    → LinearRegression.fit() → MAPE on dollars
"""
import sqlite3

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_percentage_error

from src.split import split_offers
from src.features import build_features


def load_raw():
    """
    Open data/flights.db and read offers, airports, airlines into DataFrames.
    Return (offers, airports, airlines).
    """
    # TODO: sqlite3.connect("data/flights.db")
    # TODO: pd.read_sql("SELECT * FROM offers", conn) for each table
    
    conn = sqlite3.connect("data/flights.db")
    offers = pd.read_sql("SELECT * FROM offers", conn)
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
    y = df["log_price"]
    X = df.drop(columns=["log_price"])

    # 2. Dummify string/categorical columns so LR can consume them.
    # Alt encoding for month_of_year (option B): sin/cos pair instead of dummies.
    #   X["month_sin"] = np.sin(2*np.pi * X["month_of_year"] / 12)
    #   X["month_cos"] = np.cos(2*np.pi * X["month_of_year"] / 12)
    # Dummies treat Dec and Jan as unrelated buckets; sin/cos preserves adjacency.
    # Useful when the chronological split leaves some months only in test —
    # sin/cos interpolates while dummies just zero out. Baseline uses dummies;
    # revisit if test-set months mostly fall outside train coverage.
    X = pd.get_dummies(X, columns=["airline", "airline_type", "day_of_week", "month_of_year"])

    # 3. On val/test, force X to match train's column set (same names, same order).
    #    Missing columns -> filled with 0. New columns in val/test -> dropped.
    #    On train (train_columns=None), skip this — X.columns IS the source of truth.
    if train_columns is not None:
        X = X.reindex(columns=train_columns, fill_value=0)

    return X, y, X.columns



def evaluate(model, X, y_log, label):
    """
    Predict, inverse the log transform, compute MAPE on dollar space.
    Print the result with the given label (e.g. "train", "val").
    """
    # TODO: log_pred = model.predict(X)
    # TODO: dollar_pred = np.exp(log_pred)
    # TODO: dollar_true = np.exp(y_log)
    # TODO: mape = mean_absolute_percentage_error(dollar_true, dollar_pred)
    # TODO: print(f"{label} MAPE: {mape:.3f}")
    ...


def main():
    offers, airports, airlines = load_raw()

    # 1. Split RAW offers chronologically (BEFORE feature engineering)
    train_offers, val_offers, test_offers = split_offers(offers)

    # 2. Build features — FIT route_means on train, APPLY to val/test
    train_df, route_means = build_features(train_offers, airports, airlines, route_means=None)
    val_df,   _ = build_features(val_offers,   airports, airlines, route_means=route_means)
    test_df,  _ = build_features(test_offers,  airports, airlines, route_means=route_means)

    # 3. Convert to (X, y). Capture train's column set so val/test align.
    X_train, y_train, train_cols = prepare_xy(train_df, train_columns=None)
    X_val,   y_val,   _          = prepare_xy(val_df,   train_columns=train_cols)
    # test held out — don't touch until you've stopped tuning

    # 4. Fit
    model = LinearRegression()
    model.fit(X_train, y_train)

    # 5. Evaluate on train + val only
    evaluate(model, X_train, y_train, "train")
    evaluate(model, X_val,   y_val,   "val")


if __name__ == "__main__":
    main()
