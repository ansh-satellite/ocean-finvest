import pandas as pd
import os

path = r"c:\Users\LENOVO\Desktop\Ocean Finvest\NAV.xlsx"
if os.path.exists(path):
    try:
        xl = pd.ExcelFile(path)
        print("Sheets:", xl.sheet_names)
        for sheet in xl.sheet_names:
            df = xl.parse(sheet)
            print(f"\n--- Sheet: {sheet} ---")
            print(df.head())
    except Exception as e:
        print("Error reading Excel:", e)
else:
    print("File not found")
