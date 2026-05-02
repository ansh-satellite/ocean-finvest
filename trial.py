import pandas as pd
from datetime import datetime

# Load your data
df = pd.read_excel(r"C:/Users/LENOVO/Desktop/Ocean Finvest/Momentum_Maxfolio.xlsx")
df.columns = df.columns.str.strip()
df["Date"] = pd.to_datetime(df["Date"])

today = pd.Timestamp.today().normalize()
print("TODAY:", today)
print()

# Check BANKINDIA specifically
ticker = "BANKINDIA"
snap = df[df["Ticker"] == ticker].sort_values("Date")
print(f"All dates for {ticker}:")
print(snap["Date"].dt.normalize().unique())
print()

available_dates = sorted(snap["Date"].dt.normalize().unique())
prev_dates = [d for d in available_dates if d < today]
print("Dates BEFORE today:", prev_dates)
print("Max prev date (should be yesterday):", max(prev_dates) if prev_dates else "NONE")
print()

# Show what rows exist on that prev date
if prev_dates:
    prev_date = max(prev_dates)
    prev_rows = snap[snap["Date"].dt.normalize() == prev_date]
    print(f"Rows on {prev_date}:")
    print(prev_rows[["Date", "Close", "Buy_Hold_Value"]])