from truedata_ws.websocket.TD import TD
import pandas as pd
from datetime import datetime

# Credentials
TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

def fetch_and_export_bse500():
    # Initialize TrueData Historical API
    td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None, historical_api=True)
    
    symbol = "BSE500"
    start_time = datetime(2026, 3, 30, 9, 15)
    end_time = datetime(2026, 4, 24, 15, 30)
    
    print(f"Fetching {symbol} daily data from {start_time} to {end_time}...")
    
    try:
        # Fetch EOD (End of Day) bars for the last 2 months to cover our range
        hist = td.get_historic_data(symbol, duration="2 M", bar_size="EOD")
        
        if not hist:
            print("No data received from TrueData.")
            return

        df = pd.DataFrame(hist)
        
        # Clean up columns
        column_map = {
            'time': 'Date',
            'o': 'Open',
            'h': 'High',
            'l': 'Low',
            'c': 'Close',
            'v': 'Volume',
            'oi': 'OI'
        }
        df = df.rename(columns=column_map)
        
        # Format Date and Filter
        df['Date'] = pd.to_datetime(df['Date'])
        
        # Filter for March 30 to April 24
        mask = (df['Date'] >= '2026-03-30') & (df['Date'] <= '2026-04-24')
        df = df[mask].copy()
        
        df['Date'] = df['Date'].dt.date
        
        # Export to CSV
        output_file = "BSE500_Daily_Data.csv"
        df.to_csv(output_file, index=False)
        
        print(f"Successfully exported {len(df)} rows to {output_file}")
        print(df.head())
        
    except Exception as e:
        print(f"Error occurred: {e}")
    finally:
        td.disconnect()

if __name__ == "__main__":
    fetch_and_export_bse500()
