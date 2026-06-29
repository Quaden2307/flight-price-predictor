COLUMNS_TO_CLEAN = ["Year","quarter","citymarketid_1","citymarketid_2","nsmiles","passengers","fare","large_ms","fare_lg","lf_ms","fare_low"] #outdated
ROWS_TO_INCLUDE = 7003 #outdated
COLUMNS_TO_KEEP = ["Year","quarter","citymarketid_1","citymarketid_2","city1","city2","nsmiles","passengers","fare","carrier_lg","large_ms","fare_lg","carrier_low","lf_ms","fare_low"] #outdated


# ─────────────────────────────────────────────────────────────────────────────
# Live-pipeline config (SQLite `offers`). The constants above belong to the
# legacy Phase-1 CSV path; everything below is for the current modeling pipeline.
#
# FROZEN SPLIT — so every run sees the same rows split the same way. Without this,
# split.py recomputed the train/val/test cutoffs from the daily-growing DB on each
# run, so no two runs were comparable (a change's score delta was confounded with
# data growth). See memory note: eval-regime-and-012-verdict.
# ─────────────────────────────────────────────────────────────────────────────

# Train/val/test boundaries by DEPARTURE date. These were the 0.70 / 0.85
# quantiles of departure_at on 2026-06-28; now frozen as fixed calendar dates so
# a given flight always lands in the same pile no matter how large the DB grows.
VAL_CUTOFF = "2026-08-06"    # departs before this            -> train
TEST_CUTOFF = "2026-09-12"   # departs in [VAL_CUTOFF, this)  -> val ; on/after -> test

# Data snapshot by CAPTURE date: only use offers captured on or before this date,
# so the dataset stops growing under your experiments. Bump it DELIBERATELY when
# you want to fold in newly collected data, then re-establish the baseline.
SNAPSHOT_DATE = "2026-06-28"