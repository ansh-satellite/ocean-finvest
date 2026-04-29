import pandas as pd
import os

path = r"c:\Users\LENOVO\Desktop\Ocean Finvest\NAV.xlsx"
if os.path.exists(path):
    try:
        df = pd.read_excel(path)
        print("Columns:", df.columns.tolist())
        print("First 5 rows:\n", df.head())
        print("Last 5 rows:\n", df.tail())
    except Exception as e:
        print("Error reading Excel:", e)
else:
    print("File not found")
