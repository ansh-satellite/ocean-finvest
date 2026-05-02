import pandas as pd

def compute_calendar_returns(df: pd.DataFrame):
    df = df.copy()

    # Ensure datetime & sorting
    df["DATE"] = pd.to_datetime(df["DATE"])
    df = df.sort_values("DATE")

    # Create YearMonth
    df["YearMonth"] = df["DATE"].dt.to_period("M")

    today = pd.Timestamp.today()
    current_month = today.to_period("M")

    # 🔥 STEP 1: Check if current month is complete
    current_data = df[df["YearMonth"] == current_month]

    if not current_data.empty:
        last_date = current_data["DATE"].max()
        month_end = last_date.to_period("M").to_timestamp("M")

        # If incomplete → shift to previous month
        if last_date.normalize() != month_end.normalize():
            effective_month = current_month - 1
        else:
            effective_month = current_month
    else:
        effective_month = current_month - 1

    # 🔥 STEP 2: Decide window size
    if effective_month == current_month:
        # 6 returns
        months = [effective_month - i for i in range(6, -1, -1)]
    else:
        # 5 returns
        months = [effective_month - i for i in range(5, -1, -1)]

    rows = []

    for i in range(1, len(months)):
        ym = months[i]
        prev_ym = months[i - 1]

        current_data = df[df["YearMonth"] == ym]
        prev_data = df[df["YearMonth"] == prev_ym]

        # Determine Start NAVs
        if not prev_data.empty:
            # Standard case: Use last day of previous month
            start_port = prev_data["PORT NAV"].iloc[-1]
            start_bm = prev_data["BM NAV"].iloc[-1]
        elif ym == df["YearMonth"].min():
            # First month in dataset: Use the first ever available value
            start_port = df["PORT NAV"].iloc[0]
            start_bm = df["BM NAV"].iloc[0]
        else:
            # Gaps in data: Skip
            continue

        end_port = current_data["PORT NAV"].iloc[-1]
        end_bm = current_data["BM NAV"].iloc[-1]

        if start_port == 0 or start_bm == 0:
            continue

        port_ret = (end_port - start_port) / start_port * 100
        bm_ret = (end_bm - start_bm) / start_bm * 100

        rows.append({
            "Month": pd.to_datetime(str(ym)).strftime("%b-%y"),
            "PORT": round(port_ret, 2),
            "BSE 500": round(bm_ret, 2),
            "Alpha": round(port_ret - bm_ret, 2)
        })

    return pd.DataFrame(rows).reset_index(drop=True)