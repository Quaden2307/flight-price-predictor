#clean
import pandas as pd
from src.config import COLUMNS_TO_CLEAN, ROWS_TO_INCLUDE, COLUMNS_TO_KEEP

#string to number conversion
def clean_data(df):
    df = df[COLUMNS_TO_KEEP]
    df = df.iloc[0:ROWS_TO_INCLUDE]
    for column in COLUMNS_TO_CLEAN:
        df[column] = df[column].astype(str)
        df[column] = df[column].str.replace(",", "")
        df[column] = df[column].str.replace("$", "", regex=False)
        df[column] = pd.to_numeric(df[column], errors="coerce")
    return df
      


