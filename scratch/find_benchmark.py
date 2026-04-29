import pandas as pd
import os

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

if os.path.exists(DATA_PATH):
    try:
        df = pd.read_excel(DATA_PATH)
        tickers = df['Ticker'].unique()
        candidates = ['CNX500', 'BSE500', 'NIFTY500', 'Nifty 500', 'BSE 500']
        found = [t for t in tickers if t in candidates]
        print("Found Tickers:", found)
        
        # If not found, maybe it's in the 'Close' of some other ticker or just not there?
        # Let's check if there's any ticker that has the word '500'
        contains_500 = [t for t in tickers if '500' in str(t)]
        print("Tickers containing 500:", contains_500)
        
    except Exception as e:
        print("Error:", e)
else:
    print("DATA_PATH not found")
