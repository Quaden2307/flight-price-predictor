"""
Chronological train/val/test split for the flight price predictor.

Splits raw offers by `departure_at` so the test set simulates "future flights
the model has never seen" — matching the deployment scenario where a user
queries a flight that departs after any data the model trained on.

Used upstream of build_features() so route_means and any other fitted feature
parameters are computed on train only, then reused for val/test/inference.
"""
import pandas as pd
