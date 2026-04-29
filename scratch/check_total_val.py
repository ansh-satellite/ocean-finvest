import pandas as pd
import os

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

if os.path.exists(DATA_PATH):
    try:
        df = pd.read_excel(DATA_PATH)
        df['Date'] = pd.to_datetime(df['Date'])
        min_date = df['Date'].min()
        
        # Get unique rows for each date to check Total_Portfolio_Value
        date_summary = df.groupby('Date')['Total_Portfolio_Value'].first().reset_index()
        
        print("Date Summary (First 10):")
        print(date_summary.head(10))
        
        initial_val = date_summary.iloc[0]['Total_Portfolio_Value']
        print(f"Initial Total Portfolio Value on {min_date}: {initial_val}")
        
    except Exception as e:
        print("Error:", e)
else:
    print("DATA_PATH not found")
