import pandas as pd
import os

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

if os.path.exists(DATA_PATH):
    try:
        df = pd.read_excel(DATA_PATH)
        df['Date'] = pd.to_datetime(df['Date'])
        min_date = df['Date'].min()
        max_date = df['Date'].max()
        
        initial_val = df[df['Date'] == min_date]['Buy_Hold_Value'].sum()
        current_val = df[df['Date'] == max_date]['Buy_Hold_Value'].sum()
        
        print(f"Min Date: {min_date}")
        print(f"Max Date: {max_date}")
        print(f"Initial Value on {min_date}: {initial_val}")
        print(f"Current Value on {max_date}: {current_val}")
        
    except Exception as e:
        print("Error:", e)
else:
    print("DATA_PATH not found")
