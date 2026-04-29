from truedata_ws.websocket.TD import TD
import pandas as pd
from datetime import datetime

TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

def check_historical_benchmark():
    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)
        # Fetch EOD data for BSE500 from April 3, 2023
        # Since April 3, 2023 to April 23, 2026 is about 3 years.
        # ~250 trading days per year * 3 = 750 bars.
        bars = td.get_n_historical_bars("BSE500", no_of_bars=1000, bar_size="EOD")
        if bars:
            df = pd.DataFrame(bars)
            print(f"Fetched {len(df)} bars for BSE500")
            print("First bar:", df.iloc[0]['date'], df.iloc[0]['close'])
            print("Last bar:", df.iloc[-1]['date'], df.iloc[-1]['close'])
        else:
            print("No bars fetched")
    except Exception as e:
        print("Error:", e)
    finally:
        if td:
            td.disconnect()

if __name__ == "__main__":
    check_historical_benchmark()
