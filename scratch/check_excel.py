import pandas as pd
import os

files = ["stocks_with_sectors.xlsx", "Sectorwise_equity_allocation.xlsx", "mcap_wise_stock_allocation.xlsx"]

for f in files:
    if os.path.exists(f):
        print(f"--- {f} ---")
        df = pd.read_excel(f)
        print("Columns:", df.columns.tolist())
        print(df.head())
        print("\n")
    else:
        print(f"--- {f} NOT FOUND ---")
