from truedata_ws.websocket.TD import TD
import pandas as pd
from datetime import datetime

TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None, historical_api=True)
try:
    hist = td.get_historic_data("BSE500", duration="2 M")
    df = pd.DataFrame(hist)
    if not df.empty:
        df["date"] = pd.to_datetime(df["time"]).dt.normalize()
        print("April dates:", df[df["date"].dt.month == 4]["date"].unique()[-5:])
        print("March dates:", df[df["date"].dt.month == 3]["date"].unique()[-5:])
    else:
        print("Empty DF")
except Exception as e:
    print(f"Error: {e}")
finally:
    td.disconnect()
