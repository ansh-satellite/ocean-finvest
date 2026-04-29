path = r"C:\Users\LENOVO\Desktop\Ocean Finvest\nav_updater.py"

with open(path, "rb") as f:
    raw = f.read()

src = raw.decode("utf-8")

old_func = (
    'def _compute_calendar(df: pd.DataFrame) -> pd.DataFrame:\r\n'
    '    """\r\n'
    '    For each month:\r\n'
    '      - Find the first available date in that month\r\n'
    '      - Use the NAV of the day just before that date as the base\r\n'
    '      - Use the last available date in that month as the end\r\n'
    '      Return = (end NAV - base NAV) / base NAV * 100\r\n'
    '    For the very first month (no prior data), first date of month is used as base.\r\n'
    '    For current incomplete month, latest available row is used as end.\r\n'
    '    """\r\n'
    '    df = df.copy()\r\n'
    '    df["YearMonth"] = df["DATE"].dt.to_period("M")\r\n'
    '    rows = []\r\n'
    '    for ym, grp in df.groupby("YearMonth"):\r\n'
    '        grp = grp.sort_values("DATE")\r\n'
    '        first_date = grp["DATE"].iloc[0]\r\n'
    '        prev_rows  = df[df["DATE"] < first_date]\r\n'
    '        if prev_rows.empty:\r\n'
    '            sp, sb = grp["PORT NAV"].iloc[0], grp["BM NAV"].iloc[0]\r\n'
    '        else:\r\n'
    '            sp, sb = prev_rows["PORT NAV"].iloc[-1], prev_rows["BM NAV"].iloc[-1]\r\n'
    '        ep, eb = grp["PORT NAV"].iloc[-1], grp["BM NAV"].iloc[-1]\r\n'
    '        pr = round((ep - sp) / sp * 100, 2) if sp else 0\r\n'
    '        br = round((eb - sb) / sb * 100, 2) if sb else 0\r\n'
    '        rows.append({"Month": str(ym), "PORT Ret%": pr, "BM Ret%": br, "Alpha%": round(pr - br, 2)})\r\n'
    '    return pd.DataFrame(rows)\r\n'
)

new_func = (
    'def _compute_calendar(df: pd.DataFrame) -> pd.DataFrame:\r\n'
    '    if df.empty:\r\n'
    '        return pd.DataFrame(columns=["Month", "PORT Ret%", "BM Ret%", "Alpha%"])\r\n'
    '        \r\n'
    '    df_calc = df.copy()\r\n'
    '    df_calc["YearMonth"] = df_calc["DATE"].dt.to_period("M")\r\n'
    '    min_month = df_calc["YearMonth"].min()\r\n'
    '    max_month = df_calc["YearMonth"].max()\r\n'
    '    all_months = pd.period_range(min_month, max_month, freq="M")\r\n'
    '    \r\n'
    '    rows = []\r\n'
    '    for ym in all_months:\r\n'
    '        grp = df_calc[df_calc["YearMonth"] == ym]\r\n'
    '        \r\n'
    '        if grp.empty:\r\n'
    '            rows.append({"Month": str(ym), "PORT Ret%": 0.0, "BM Ret%": 0.0, "Alpha%": 0.0})\r\n'
    '            continue\r\n'
    '            \r\n'
    '        grp = grp.sort_values("DATE")\r\n'
    '        first_date = grp["DATE"].iloc[0]\r\n'
    '        prev_rows  = df_calc[df_calc["DATE"] < first_date]\r\n'
    '        if prev_rows.empty:\r\n'
    '            sp, sb = grp["PORT NAV"].iloc[0], grp["BM NAV"].iloc[0]\r\n'
    '        else:\r\n'
    '            sp, sb = prev_rows["PORT NAV"].iloc[-1], prev_rows["BM NAV"].iloc[-1]\r\n'
    '            \r\n'
    '        ep, eb = grp["PORT NAV"].iloc[-1], grp["BM NAV"].iloc[-1]\r\n'
    '        \r\n'
    '        pr = round((ep - sp) / sp * 100, 2) if sp else 0\r\n'
    '        br = round((eb - sb) / sb * 100, 2) if sb else 0\r\n'
    '        rows.append({"Month": str(ym), "PORT Ret%": pr, "BM Ret%": br, "Alpha%": round(pr - br, 2)})\r\n'
    '        \r\n'
    '    return pd.DataFrame(rows)\r\n'
)

src2 = src.replace(old_func, new_func, 1)
if src2 != src:
    with open(path, "wb") as f:
        f.write(src2.encode("utf-8"))
    print("SUCCESS: _compute_calendar replaced!")
else:
    print("ERROR: Could not match the _compute_calendar function string exactly.")
