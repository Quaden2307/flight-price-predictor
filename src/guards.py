"""
Safeguards for the modeling pipeline: loud failures where pandas stays quiet.

Why this module exists (documentation/archive/modeling_runs_prefreeze_2026-06-30.md,
Note A): the first three modeling runs trained on ~6k of ~68k rows. The airports
table lacked the metro/city codes the API labels offers with (NYC, TYO, YTO),
so build_features' coordinate merges produced NaN, dropna() removed ~92% of the
rows, and nothing raised. The numbers looked plausible. The bug only surfaced
when the row counts in the run log were compared against the database.

Both checks here are cheap and run on every build_features() call:

    check_airport_coverage()  every origin/destination code in the offers must
                              exist in the airports table. Fails listing the
                              missing codes and how many rows each one touches.
    guarded_dropna()          dropna with a receipt: rows before/after, NaNs per
                              column, and a hard failure when the loss exceeds
                              MAX_FEATURE_DROP_FRAC (src/config.py).

Also runnable on their own against the live DB (do this after any route change):

    venv/bin/python -m src.check_coverage

If a guard trips, fix the data or the reference table. Do not raise the ceiling
to make a run pass; that recreates the original failure with extra steps.
"""
import pandas as pd


class GuardError(RuntimeError):
    """A pipeline safeguard tripped. The message says what to fix."""


def airport_code_counts(offers_df):
    """Rows per IATA code, counting a row once for its origin and once for its destination."""
    origin = offers_df["origin"].value_counts()
    destination = offers_df["destination"].value_counts()
    return origin.add(destination, fill_value=0).astype(int).sort_values(ascending=False)


def check_airport_coverage(offers_df, airports_df, label="offers"):
    """
    Every code in offers.origin / offers.destination must be a row in the
    airports table, or add_features()'s left-merges yield NaN coordinates and
    the row is lost downstream.

    Returns the (empty) Series of missing codes on success so callers can
    reuse it in reports. Raises GuardError listing codes, row counts and the fix.
    """
    counts = airport_code_counts(offers_df)
    known = set(airports_df["iata"])
    missing = counts[~counts.index.isin(known)]

    if missing.empty:
        print(f"[guard] airport coverage ({label}): {len(counts)} codes, all present in airports table")
        return missing

    touched = offers_df["origin"].isin(missing.index) | offers_df["destination"].isin(missing.index)
    affected = int(touched.sum())
    frac = affected / len(offers_df) if len(offers_df) else 0.0
    per_code = "\n  ".join(f"{code}: {n} rows" for code, n in missing.items())
    raise GuardError(
        f"[guard] airport coverage ({label}): {len(missing)} code(s) missing from the airports table, "
        f"touching {affected} of {len(offers_df)} rows ({frac:.1%}). "
        f"build_features would drop these rows without an error.\n"
        f"  {per_code}\n"
        f"  Fix: real airports -> EXTRA_AIRPORT_CODES, metro codes -> CITY_CODES in "
        f"data_collector/populate_airports.py, re-run it, then re-run this check."
    )


def guarded_dropna(df, subset, max_drop_frac, label="dropna"):
    """
    df.dropna(subset=...) that reports what it removed and refuses to remove
    too much.

    Legitimate losses on this pipeline are small: cold-start routes in val/test
    whose route_mean_log_price is NaN, roughly 0.2-0.4% of rows. A loss above
    max_drop_frac means a join or a reference table broke upstream, which is
    exactly the failure that produced the ~6k-row training set in June 2026.
    """
    before = len(df)
    if before == 0:
        raise GuardError(f"[guard] {label}: received 0 rows; nothing upstream should hand this an empty frame")

    nan_by_column = df[subset].isna().sum()
    out = df.dropna(subset=subset)
    dropped = before - len(out)
    frac = dropped / before
    detail = ", ".join(f"{col}={int(n)}" for col, n in nan_by_column.items())

    print(f"[guard] {label}: {before} -> {len(out)} rows (dropped {dropped}, {frac:.2%}) | NaN by column: {detail}")

    if frac > max_drop_frac:
        worst = nan_by_column.idxmax()
        raise GuardError(
            f"[guard] {label}: dropped {dropped} of {before} rows ({frac:.1%}), above the "
            f"{max_drop_frac:.1%} ceiling (MAX_FEATURE_DROP_FRAC in src/config.py).\n"
            f"  NaN by column: {detail}\n"
            f"  Most NaNs are in '{worst}'. If that is distance_km or is_international, an airport "
            f"code is missing from the airports table (run: python -m src.check_coverage). "
            f"If it is route_mean_log_price, the route_means you passed do not match this data."
        )
    return out
