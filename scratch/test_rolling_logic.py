import pandas as pd
from datetime import datetime, timedelta
import os

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

def test_logic():
    if not os.path.exists(DATA_PATH):
        print(f"File not found: {DATA_PATH}")
        return

    df = pd.read_excel(DATA_PATH)
    df['Date'] = pd.to_datetime(df['Date'])
    df.columns = df.columns.str.strip()
    
    print(f"Data loaded. Shape: {df.shape}")
    print(f"Date range: {df['Date'].min()} to {df['Date'].max()}")
    
    today = datetime.today()
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    months = []
    for i in range(6):
        target = current_month_start
        for _ in range(i):
            target = (target - timedelta(days=1)).replace(day=1)
        months.append(target)
    
    print(f"Rolling 6 months: {[m.strftime('%B %Y') for m in months]}")
    
    tickers = df['Ticker'].unique()[:5] # Test first 5
    for ticker in tickers:
        ticker_df = df[df['Ticker'] == ticker].sort_values('Date')
        print(f"\nTicker: {ticker}")
        for m_start in months:
            m_end = (m_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            month_data = ticker_df[(ticker_df['Date'] >= m_start) & (ticker_df['Date'] <= m_end)]
            if not month_data.empty:
                s_price = month_data.iloc[0]['Open']
                e_price = month_data.iloc[-1]['Close']
                print(f"  {m_start.strftime('%b %Y')}: Start={s_price}, End={e_price}")
            else:
                print(f"  {m_start.strftime('%b %Y')}: No data")

if __name__ == "__main__":
    test_logic()
