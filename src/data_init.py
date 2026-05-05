#data_init
import pandas as pd
from pathlib import Path

def load_data():
    base_dir = Path(__file__).resolve().parent  # src/
    data_path = base_dir.parent / "data" / "flights.csv"

    return pd.read_csv(data_path)
