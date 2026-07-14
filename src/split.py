"""
Chronological train/val/test split for the flight price predictor.

Splits raw offers by `departure_at` so the test set simulates "future flights
the model has never seen" — matching the deployment scenario where a user
queries a flight that departs after any data the model trained on.

Used upstream of build_features() so route_means and any other fitted feature
parameters are computed on train only, then reused for val/test/inference.
"""
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

from src.config import VAL_CUTOFF, TEST_CUTOFF

def split_offers(offers):
    departure = pd.to_datetime(offers["departure_at"].str[:19])
    # Frozen calendar cutoffs (src/config.py) instead of live quantiles, so the
    # split boundaries don't drift as the DB grows.
    val_cutoff = pd.Timestamp(VAL_CUTOFF)
    test_cutoff = pd.Timestamp(TEST_CUTOFF)

    train = offers[departure < val_cutoff]
    val = offers[(departure >= val_cutoff) & (departure < test_cutoff)]
    test = offers[departure >= test_cutoff]

    return train, val, test


def split_offers_grouped(offers, val_size=0.2, seed=0):
    """
    Date-grouped train/val split (run #9 regime); test stays chronological.

    Whole trips (origin+destination+departure_at) are dealt randomly to train
    or val, so val has the same month / lead-time mix as train and differs in
    exactly one way: the model never saw these trips. That matches the product
    question ("price a flight you've never seen") instead of the old calendar
    split's far-future-extrapolation quiz.

    Departures on/after TEST_CUTOFF are carved off FIRST, untouched — the
    final exam stays a true future window.
    """
    departure = pd.to_datetime(offers["departure_at"].str[:19])
    test_cutoff = pd.Timestamp(TEST_CUTOFF)

    test = offers[departure >= test_cutoff]
    pool = offers[departure < test_cutoff]

    # Trip label. Coarser than itinerary_id on purpose (no return_at): offers
    # sharing an outbound flight stay on the same side of the split.
    groups = pool["origin"] + "|" + pool["destination"] + "|" + pool["departure_at"]

    # One random deal of whole trips, frozen by the seed. test_size is a
    # fraction of TRIPS, so row counts land near-but-not-exactly 20%.
    gss = GroupShuffleSplit(n_splits=1, test_size=val_size, random_state=seed)
    train_idx, val_idx = next(gss.split(pool, groups=groups))

    # Positional indices -> .iloc (pool's index has gaps after the filter).
    train = pool.iloc[train_idx]
    val = pool.iloc[val_idx]

    # The whole point of this split — verify it, don't assume it.
    overlap = set(groups.iloc[train_idx]) & set(groups.iloc[val_idx])
    assert not overlap, f"{len(overlap)} trips appear in BOTH train and val"

    return train, val, test
