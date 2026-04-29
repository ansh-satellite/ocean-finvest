from truedata_ws.websocket.TD import TD
import pandas as pd

TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None, historical_api=True)
try:
    hist = td.get_historic_data("BSE500", duration="2 M")
    df = pd.DataFrame(hist)
    print("Columns:", df.columns.tolist())
    price_col = None
    for col in ["close", "Close", "c", "ltp"]:
        if col in df.columns:
            price_col = col
            break
    print("Price Col:", price_col)
    
    if price_col:
        df["date"] = pd.to_datetime(df["time"]).dt.normalize()
        today = pd.Timestamp.today().normalize()
        current_month = today.to_period("M")
        prev_month = current_month - 1
        
        curr_df = df[df["date"].dt.to_period("M") == current_month]
        prev_df = df[df["date"].dt.to_period("M") == prev_month]
        
        print("Curr DF size:", len(curr_df))
        print("Prev DF size:", len(prev_df))
        
        if not curr_df.empty:
            curr_dates = sorted(curr_df["date"].unique())
            current_date = curr_dates[-1]
            current_val = curr_df[curr_df["date"] == current_date][price_col].iloc[-1]
            print(f"Current: {current_date} -> {current_val}")
            
        if not prev_df.empty:
            prev_dates = sorted(prev_df["date"].unique())
            base_date = prev_dates[-1]
            base_val = prev_df[prev_df["date"] == base_date][price_col].iloc[-1]
            print(f"Base: {base_date} -> {base_val}")
            
except Exception as e:
    print(f"Error: {e}")
finally:
    td.disconnect()
