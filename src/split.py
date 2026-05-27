"""
Chronological train/val/test split for the flight price predictor.

Splits raw offers by `departure_at` so the test set simulates "future flights
the model has never seen" — matching the deployment scenario where a user
queries a flight that departs after any data the model trained on.

Used upstream of build_features() so route_means and any other fitted feature
parameters are computed on train only, then reused for val/test/inference.
"""
import pandas as pd

def split_offers(offers):
    departure = pd.to_datetime(offers["departure_at"].str[:19])
    val_cutoff = departure.quantile(0.70)
    test_cutoff = departure.quantile(0.85)

    train = offers[departure < val_cutoff]
    val = offers[(departure >= val_cutoff) & (departure < test_cutoff)]
    test = offers[departure >= test_cutoff]

    return train, val, test
