import pandas as pd
DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Momentum_Maxfolio.xlsx"
df = pd.read_excel(DATA_PATH)
df["Date"] = pd.to_datetime(df["Date"])
print("Last 5 dates in Maxfolio:", df["Date"].unique()[-5:])
