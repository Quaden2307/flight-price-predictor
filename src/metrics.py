"""
Scoring utilities shared by every trainer (LR, XGBoost, ...).

Pure functions: arrays in, numbers out. No models, no DB, no file I/O —
so anything here can be unit-tested with a handful of fake numbers.
"""
import numpy as np
import pandas as pd


def bootstrap_mape_ci(y_true, y_pred, groups, n_boot=1000, seed=0):
    """
    95% confidence interval for MAPE, resampling whole itineraries.

    Rows sharing an itinerary_id are near-duplicate captures of the same
    physical flight. Resampling individual ROWS would make every draw look
    alike (the duplicates smooth it out) and report a dishonestly narrow
    interval. So each draw picks whole ITINERARIES with replacement and
    carries all of their rows along — duplicates travel as one unit.

    Parameters
    ----------
    y_true, y_pred : array-like
        Actual and predicted prices in DOLLARS (not log), same length.
    groups : array-like
        itinerary_id per row, aligned with y_true / y_pred.
    n_boot : int
        Number of bootstrap draws.
    seed : int
        Fixes the random draws — same seed, same data -> identical interval.

    Returns
    -------
    (low, high) : 2.5th / 97.5th percentiles of the n_boot MAPEs.
    """
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)

    # Lookup: itinerary -> integer positions of its rows. Kept as a list of
    # position-arrays; the draws below index into it.
    buckets = list(pd.DataFrame({"g": np.asarray(groups)}).groupby("g").indices.values())
    n_groups = len(buckets)

    rng = np.random.default_rng(seed)

    mapes = []
    for _ in range(n_boot):
        # One pretend val set: n_groups itineraries drawn WITH replacement
        # (some picked twice, some skipped — that's what creates the wobble).
        picked = rng.integers(0, n_groups, size=n_groups)
        rows = np.concatenate([buckets[i] for i in picked])
        ape = np.abs(y_true[rows] - y_pred[rows]) / y_true[rows]
        mapes.append(ape.mean())

    low, high = np.percentile(mapes, [2.5, 97.5])
    return low, high
