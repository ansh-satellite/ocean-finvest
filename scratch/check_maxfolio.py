import pandas as pd
import os

path = r"c:\Users\LENOVO\Desktop\Ocean Finvest\Momentum_Maxfolio.xlsx"
if os.path.exists(path):
    try:
        xl = pd.ExcelFile(path)
        print("Sheets:", xl.sheet_names)
        for sheet in xl.sheet_names[:3]: # check first 3 sheets
            df = xl.parse(sheet)
            print(f"\n--- Sheet: {sheet} ---")
            print("Columns:", df.columns.tolist())
            print(df.head())
    except Exception as e:
        print("Error reading Excel:", e)
else:
    print("File not found")
