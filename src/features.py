"""
Feature engineering for the flight price predictor.

Single source of truth for the transformations that turn raw `offers` rows
(plus the `airports` and `airlines` reference tables) into the modeling
DataFrame. Both training and inference call into this module so the same
feature definitions are used in both contexts.

Layout — one shared core, two entry points:

    add_features()          shared feature math. Never touches `price` — a
                            serving query has no price (it's the thing being
                            predicted), so anything price-shaped lives outside
                            the core and the two paths can't drift apart.
    build_features()        training path: log_price target, FITS route_means
                            (if not passed), Tier-B merges, itinerary_id
                            label, dropna.
    build_query_features()  serving path: no target, route_means is REQUIRED
                            (there is deliberately no None default — fitting
                            at inference would be target leakage), explicit
                            errors instead of dropna, cold-start fallback for
                            routes the model never saw.
    prepare_x()             shared (X, columns) prep: drop non-features,
                            dummify, align to the training column set.
    prepare_xy()            training wrapper: prepare_x + the log_price target.
"""
import datetime as dt
from math import radians, sin, cos, asin, sqrt

import numpy as np
import pandas as pd

# Columns present in a training DataFrame that must never enter X.
# log_price is the target; itinerary_id is a grouping label for the bootstrap
# CI (metrics.py); airline / airline_type / transfers are Tier-B offer
# outcomes — not known at query time, so deployable models can't use them.
NON_FEATURE_COLUMNS = ["log_price", "itinerary_id", "airline", "airline_type", "transfers"]


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


def add_features(df, airports_df, route_means):
    """
    Shared feature core: everything computable from route + dates alone
    (the Tier-A contract). Called by BOTH build_features (training) and
    build_query_features (serving) — this function must never read `price`
    or `log_price`, because the serving path doesn't have them.

    Needs on df: origin, destination, departure_at, lead_time_days.
    `route_means` is always the FITTED mapping — fitting happens upstream,
    on the training path only.
    """
    # 1. Merge airports_df on origin iata -> origin_country, origin_lat, origin_lon
    origin_ap = airports_df.rename(columns={
        "iata": "origin",
        "country": "origin_country",
        "latitude": "origin_lat",
        "longitude": "origin_lon",
    })[["origin", "origin_country", "origin_lat", "origin_lon"]]
    df = df.merge(origin_ap, on="origin", how="left")

    # 2. Same merge on destination iata
    destination_ap = airports_df.rename(columns={
        "iata": "destination",
        "country": "destination_country",
        "latitude": "destination_lat",
        "longitude": "destination_lon",
    })[["destination", "destination_country", "destination_lat", "destination_lon"]]
    df = df.merge(destination_ap, on="destination", how="left")

    # 3. is_international: 1 if origin_country != destination_country else 0
    df["is_international"] = (df["origin_country"] != df["destination_country"]).astype(int)

    # 4. distance_km: haversine(origin, destination)
    df["distance_km"] = df.apply(
        lambda r: haversine_km(r["origin_lat"], r["origin_lon"], r["destination_lat"], r["destination_lon"]),
        axis=1
    )

    # 5. day_of_week / month_of_year: parse departure_at as local wall-clock
    #    (strip tz offset), take day name / month int
    local_departure = pd.to_datetime(df["departure_at"].astype(str).str[:19])
    df["day_of_week"] = local_departure.dt.day_name()
    df["month_of_year"] = local_departure.dt.month

    # 6. route_mean_log_price: APPLY the fitted mapping. Unseen routes come
    #    out NaN here — training drops them (dropna), serving fills them with
    #    an explicit cold-start fallback.
    route_means_df = (
        route_means.rename("route_mean_log_price").reset_index()
    )
    df = df.merge(route_means_df, on=["origin", "destination"], how="left")

    return df


def build_features(offers_df, airports_df, airlines_df, route_means=None):
    """
    TRAINING path: raw offers + reference tables -> modeling DataFrame.

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
        Pass the fitted Series on val/test (function reuses it).

    Returns
    -------
    (modeling_df, route_means) : tuple
        modeling_df : one row per offer, target + features.
        route_means : the fitted mapping (newly computed if was None, else passed-through).
    """
    df = offers_df.copy()

    # 1. Target: log_price = log(price)
    df["log_price"] = np.log(df["price"])

    # 2. FIT route_means on this data if not passed (train), else reuse (val/test).
    if route_means is None:
        route_means = df.groupby(["origin", "destination"])["log_price"].mean()

    # 3. Shared Tier-A feature core (airport merges, is_international,
    #    distance_km, day/month, route_mean apply).
    df = add_features(df, airports_df, route_means)

    # 4. Tier-B: airline_type via airlines merge. Offer outcomes, training-only —
    #    a serving query has no airline column, so this stays out of the core.
    airlines = airlines_df.rename(columns={
        "iata": "airline",
        "type": "airline_type",
    })[["airline", "airline_type"]]
    df = df.merge(airlines, on="airline", how="left")
    df["airline_type"] = df["airline_type"].fillna("unknown")

    # 5. itinerary_id: which physical round-trip this row is a capture of.
    #    A grouping LABEL for clustered evaluation (metrics.py), NOT a model
    #    feature — prepare_x drops it before X is built.
    df["itinerary_id"] = (
        df["origin"] + "|" + df["destination"] + "|"
        + df["departure_at"] + "|" + df["return_at"]
    )

    # 6. Drop rows with NaN in critical columns (log_price, distance_km, lead_time_days)
    df = df.dropna(subset=["log_price", "distance_km", "lead_time_days", "route_mean_log_price"])

    # 7. Select final columns: target + features (+ itinerary_id label)
    FINAL_COLUMNS = [
        "log_price",
        "itinerary_id",
        "distance_km",
        "lead_time_days",
        "day_of_week",
        "month_of_year",
        "airline_type",
        "airline",
        "transfers",
        "is_international",
        "route_mean_log_price",
    ]
    df = df[FINAL_COLUMNS]

    return df, route_means


def build_query_features(query_df, airports_df, route_means, airport_to_city=None, as_of=None):
    """
    SERVING path: user queries -> feature DataFrame ready for prepare_x.

    A query is a question, not an observation — there is no price column, so
    no target and no route_means fitting here. `route_means` is REQUIRED and
    must be the mapping fit at training time (loaded from the model bundle).

    Parameters
    ----------
    query_df : pd.DataFrame
        One row per query. Needs: origin, destination, departure_at
        (IATA codes + date or ISO timestamp). Other columns are ignored.
    airports_df : pd.DataFrame
        The `airports` reference table (same as training).
    route_means : pd.Series
        The FITTED (origin, destination) -> mean log_price mapping from the
        model bundle (models/route_means.csv).
    airport_to_city : pd.Series or None
        airport code -> IATA CITY code (models/airport_to_city.csv). The model
        is trained on city codes — offers label JFK flights as NYC, NRT as TYO
        (the schema gotcha in CLAUDE.md). Users type airport codes, so without
        this translation every major route silently falls to the cold-start
        path. Codes not in the mapping pass through (already city codes).
    as_of : datetime.date or None
        "Today" for lead_time_days. Defaults to the actual current date;
        injectable so tests are deterministic.

    Returns
    -------
    (df, route_known) : tuple
        df : feature DataFrame (Tier-A columns only), same row order as input.
        route_known : bool Series aligned to df — False where the route was
            never seen in training and route_mean_log_price is the global
            fallback. Surface this as a low-confidence flag in the product.

    Raises
    ------
    ValueError : unknown airport code, or departure in the past. Explicit
        errors instead of training's dropna — a serving row must never
        silently vanish.
    """
    df = query_df.copy()

    # 0. Translate airport codes to the CITY codes the model was trained on
    #    (JFK -> NYC, NRT -> TYO, YYZ -> YTO). Unmapped codes pass through.
    if airport_to_city is not None:
        df["origin"] = df["origin"].map(airport_to_city).fillna(df["origin"])
        df["destination"] = df["destination"].map(airport_to_city).fillna(df["destination"])

    # 1. Validate airports up front — training drops bad rows, serving must
    #    tell the caller which code it can't price ("route not supported").
    known_codes = set(airports_df["iata"])
    bad = sorted(
        set(df["origin"]).union(df["destination"]) - known_codes
    )
    if bad:
        raise ValueError(f"unknown airport/city code(s), route not supported: {bad}")

    # 2. lead_time_days: departure date minus "today". Stored per row at
    #    capture time in training data; computed here for a query.
    if as_of is None:
        as_of = dt.date.today()
    local_departure = pd.to_datetime(df["departure_at"].astype(str).str[:19])
    df["lead_time_days"] = (local_departure.dt.normalize() - pd.Timestamp(as_of)).dt.days
    if (df["lead_time_days"] < 0).any():
        raise ValueError("departure_at is in the past — nothing to predict")

    # 3. Shared Tier-A feature core — identical math to training by construction.
    df = add_features(df, airports_df, route_means)

    # 4. Cold-start: routes never seen in training get the global mean of the
    #    per-route means as a fallback, flagged so the product can say
    #    "low confidence" instead of bouncing the user (CONTEXT.md UX decision).
    route_known = df["route_mean_log_price"].notna()
    route_known.name = "route_known"
    df["route_mean_log_price"] = df["route_mean_log_price"].fillna(route_means.mean())

    # 5. Tier-A feature columns only — same set training X starts from.
    QUERY_COLUMNS = [
        "distance_km",
        "lead_time_days",
        "day_of_week",
        "month_of_year",
        "is_international",
        "route_mean_log_price",
    ]
    return df[QUERY_COLUMNS], route_known


def prepare_x(df, train_columns=None):
    """
    Feature DataFrame -> numeric X. Shared by training and serving.

    Parameters
    ----------
    df : pd.DataFrame
        Output of build_features (training) or build_query_features (serving).
    train_columns : pd.Index or None
        On train: pass None, function returns the dummified column set.
        On val/test/serving: pass train's columns so the shapes line up.

    Returns
    -------
    (X, columns)
        X : numeric DataFrame ready for the model
        columns : the column set used (return so val/test/serving can reuse it)
    """
    # 1. Drop target + labels + Tier-B (errors="ignore": a query DataFrame
    #    never had them in the first place).
    X = df.drop(columns=NON_FEATURE_COLUMNS, errors="ignore")

    # 2. Dummify string/categorical columns so the model can consume them.
    # Alt encoding for month_of_year (option B): sin/cos pair instead of dummies.
    #   X["month_sin"] = np.sin(2*np.pi * X["month_of_year"] / 12)
    #   X["month_cos"] = np.cos(2*np.pi * X["month_of_year"] / 12)
    # Dummies treat Dec and Jan as unrelated buckets; sin/cos preserves adjacency.
    # Useful when the chronological split leaves some months only in test —
    # sin/cos interpolates while dummies just zero out. Baseline uses dummies;
    # revisit if test-set months mostly fall outside train coverage.
    X = pd.get_dummies(X, columns=["day_of_week", "month_of_year"])

    # 3. Align to train's column set (same names, same ORDER — XGBoost matches
    #    by position, so a misordered X gives silently wrong predictions).
    #    Missing columns -> 0: a single query only produces dummies for its own
    #    day/month; the other ~18 must exist as explicit zeros.
    #    On train (train_columns=None), skip — X.columns IS the source of truth.
    if train_columns is not None:
        X = X.reindex(columns=train_columns, fill_value=0)

    return X, X.columns


def prepare_xy(df, train_columns=None):
    """
    Training wrapper around prepare_x: also peel off the log_price target.
    (Target separation is leakage-critical: log_price in X = trivial perfect fit.)

    Returns (X, y, columns) — same contract train_lr/train_xgb always had.
    """
    X, columns = prepare_x(df, train_columns=train_columns)
    y = df["log_price"]
    return X, y, columns
