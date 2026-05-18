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
