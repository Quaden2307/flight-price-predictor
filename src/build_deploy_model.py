"""
Build the deployable model bundle in models/.

NOT an experiment run — never log this in modeling_runs.md. The two tracks
have opposite requirements and must not be mixed:

    experiment runs (train_lr / train_xgb): frozen SNAPSHOT_DATE, held-out
        val, comparable scores. Purpose: a fair number.
    deploy build (this script): ALL data through today, NO holdout, refit of
        the already-measured model. Purpose: the best artifact.

Because there's no holdout here, this build cannot measure its own error.
The error estimate in metadata.json is CARRIED FORWARD from run #11's
measured val score — standard pattern: measure on a holdout, refit on
everything, carry the number with its provenance.

Output (all plain formats on purpose — no pickles, so a pandas/sklearn/xgboost
upgrade can't silently corrupt the bundle):

    models/model.json          XGBoost native format (version-portable)
    models/route_means.csv     fitted (origin, destination) -> mean log price
    models/train_columns.json  ordered X column names — the order IS the contract
    models/airports.csv        reference rows build_query_features needs, so
                               the backend never touches data/flights.db
    models/airport_to_city.csv airport -> IATA city code, derived from the
                               offers themselves. The model's vocabulary is
                               CITY codes (JFK trains as NYC — CLAUDE.md
                               schema gotcha); users type airport codes.
    models/metadata.json       provenance + error numbers (what the UI reads)

Run from repo root:  venv/bin/python -m src.build_deploy_model
"""
import datetime as dt
import json
import subprocess
from pathlib import Path

import pandas as pd
from xgboost import XGBRegressor

from src.features import build_features, prepare_xy
from src.train_lr import load_raw, evaluate

MODEL_DIR = Path("models")

# Run #11's hyperparameters, verbatim (modeling_runs.md) — the deployed model
# must be the measured model, just refit on current data. Change these only
# after a logged experiment run justifies it.
XGB_PARAMS = dict(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    random_state=42,
    n_jobs=-1,
)

# Carried-forward error estimate — see module docstring.
ERROR_ESTIMATE = {
    "val_mape": 0.146,
    "val_mape_ci": [0.142, 0.150],
    "source": (
        "run #11 (modeling_runs.md): date-grouped gate, Tier-A features, "
        "itinerary-clustered bootstrap CI, 2026-06-28 snapshot. Carried "
        "forward — this build trains on all data with no holdout."
    ),
    "extrapolation_caveat": (
        "0.146 measures pricing trips like those seen in training. The same "
        "model scored ~0.205 on the retired chronological split (far-future "
        "departures). Real queries about departures beyond the training "
        "window land between the two — surface the wider number honestly."
    ),
}


def git_commit():
    sha = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True
    ).stdout.strip()
    return f"{sha} +dirty" if dirty else sha


def main():
    today = dt.date.today().isoformat()

    # All data through today — deliberately NOT the frozen SNAPSHOT_DATE.
    offers, airports, airlines = load_raw(snapshot=today)
    deploy_snapshot = offers["captured_at"].str[:10].max()
    print(f"loaded {len(offers)} offers, captures through {deploy_snapshot}")

    # No split: every row is training data. route_means and train_columns are
    # fit here and saved WITH the model — the three are one unit; regenerating
    # any of them at serving time gives silently wrong predictions.
    train_df, route_means = build_features(offers, airports, airlines, route_means=None)
    X, y, train_cols = prepare_xy(train_df, train_columns=None)
    print(f"feature matrix: {X.shape[0]} rows x {X.shape[1]} cols, {len(route_means)} routes")

    model = XGBRegressor(**XGB_PARAMS)
    model.fit(X, y)

    # In-sample MAPE only — a sanity check (expect ~0.13, near run #11's train
    # score), NOT an accuracy claim. The honest number lives in ERROR_ESTIMATE.
    train_mape = evaluate(model, X, y)
    print(f"in-sample MAPE (sanity only, no holdout): {train_mape:.3f}")

    MODEL_DIR.mkdir(exist_ok=True)
    model.save_model(str(MODEL_DIR / "model.json"))
    route_means.rename("route_mean_log_price").reset_index().to_csv(
        MODEL_DIR / "route_means.csv", index=False
    )
    (MODEL_DIR / "train_columns.json").write_text(json.dumps(list(train_cols), indent=1))
    airports[["iata", "country", "latitude", "longitude"]].to_csv(
        MODEL_DIR / "airports.csv", index=False
    )

    # Airport -> city mapping, taken from the offers themselves so it's exactly
    # the vocabulary the API (and therefore route_means) uses. Empirically 1:1
    # today; keep the most-frequent city per airport in case that ever drifts.
    pairs = pd.concat([
        offers[["origin_airport", "origin"]]
            .rename(columns={"origin_airport": "airport", "origin": "city"}),
        offers[["destination_airport", "destination"]]
            .rename(columns={"destination_airport": "airport", "destination": "city"}),
    ]).value_counts().reset_index(name="n")
    airport_to_city = (
        pairs.sort_values("n", ascending=False)
        .drop_duplicates("airport")[["airport", "city"]]
        .sort_values("airport")
    )
    airport_to_city.to_csv(MODEL_DIR / "airport_to_city.csv", index=False)

    metadata = {
        "trained_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "deploy_snapshot": deploy_snapshot,
        "commit": git_commit(),
        "n_rows": int(len(X)),
        "n_routes": int(len(route_means)),
        "xgb_params": XGB_PARAMS,
        "in_sample_mape": round(float(train_mape), 3),
        "error_estimate": ERROR_ESTIMATE,
    }
    (MODEL_DIR / "metadata.json").write_text(json.dumps(metadata, indent=1))

    print(f"\nbundle written to {MODEL_DIR}/ (model.json, route_means.csv, "
          f"train_columns.json, airports.csv, airport_to_city.csv, metadata.json)")
    print(f"commit: {metadata['commit']}")


if __name__ == "__main__":
    main()
