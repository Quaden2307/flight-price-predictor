"""
Feature engineering for the flight price predictor.

Single source of truth for the transformations that turn raw `offers` rows
(plus the `airports` and `airlines` reference tables) into the modeling
DataFrame. Both training and inference call into this module so the same
feature definitions are used in both contexts.
"""
import sqlite3
from math import radians, sin, cos, asin, sqrt
from pathlib import Path

import numpy as np
import pandas as pd


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))

def build_features(offers_df, airports_df, airlines_df, route_means=None):
    """
    Turn raw offers + reference tables into the modeling DataFrame.

    Parameters
    ----------
    offers_df : pd.DataFrame
        Rows from the `offers` table.
    airports_df : pd.DataFrame
        Rows from the `airports` table. Needs: iata, country, latitude, longitude.
    airlines_df : pd.DataFrame
        Rows from the `airlines` table. Needs: iata, airline_type.
    route_means : pd.Series or None
        Mapping (origin, destination) -> mean log_price, fit on training set.
        Pass None on the training path (function computes it).
        Pass the fitted Series on val/test/inference (function reuses it).

    Returns
    -------
    (modeling_df, route_means) : tuple
        modeling_df : one row per offer, target + features.
        route_means : the fitted mapping (newly computed if was None, else passed-through).
    """

    df = offers_df.copy()


    # 1. Target: log_price = log(price)
    df["log_price"] = np.log(df["price"])

    # 2. Merge airports_df onto df on origin iata -> origin_country, origin_lat, origin_lon
    origin_ap = airports_df.rename(columns={
    "iata": "origin",
    "country": "origin_country",
    "latitude": "origin_lat",
    "longitude": "origin_lon",
    })[["origin", "origin_country", "origin_lat", "origin_lon"]]
    df = df.merge(origin_ap, on="origin", how="left")

    # 3. Merge airports_df onto df on destination iata -> destination_country, destination_lat, destination_lon
    destination_ap = airports_df.rename(columns={
    "iata": "destination",
    "country": "destination_country",
    "latitude": "destination_lat",
    "longitude": "destination_lon",
    })[["destination", "destination_country", "destination_lat", "destination_lon"]]
    df = df.merge(destination_ap, on="destination", how="left")
    
    # 4. is_international: 1 if origin_country != destination_country else 0
    df["is_international"] = (df["origin_country"] != df["destination_country"]).astype(int)

    # 5. distance_km: haversine(origin_lat, origin_lon, destination_lat, destination_lon)

    # 6. Merge airlines_df on airline iata -> airline_type. Fill NaN with "unknown".

    # 7. day_of_week: parse departure_at as local wall-clock (strip tz offset), take day name

    # 8. month_of_year: parse departure_at, take month as int

    # 9. route_mean_log_price:
    #    if route_means is None: route_means = df.groupby(["origin","destination"])["log_price"].mean()
    #    merge route_means into df as a new column

    # 10. Drop rows with NaN in critical columns (log_price, distance_km, lead_time_days)

    # 11. Select final columns: target + features

    return df, route_means
