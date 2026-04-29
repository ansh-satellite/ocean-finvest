import pandas as pd
import os

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

if os.path.exists(DATA_PATH):
    try:
        df = pd.read_excel(DATA_PATH)
        print("Unique Tickers:", df['Ticker'].unique().tolist())
    except Exception as e:
        print("Error:", e)
else:
    print("DATA_PATH not found")
