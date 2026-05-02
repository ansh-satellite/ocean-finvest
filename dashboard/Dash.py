# =========================================================
# 🚀 LIVE NAV DASHBOARD — BUY & HOLD METHOD + BENCHMARK + ALPHA
# =========================================================

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import os
from truedata_ws.websocket.TD import TD

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
# Use relative paths for portability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
NAV_FILE_PATH  = os.path.join(DATA_DIR, "NAV.xlsx")
DATA_PATH      = os.path.join(DATA_DIR, "Momentum_Maxfolio.xlsx")
REFRESH_MINUTES = 15

try:
    TD_USERNAME = st.secrets["truedata"]["username"]
    TD_PASSWORD = st.secrets["truedata"]["password"]
except Exception:
    TD_USERNAME = "tdwsf695"
    TD_PASSWORD = "ocean@695"

st.set_page_config(page_title="NAV Dashboard", page_icon="📊", layout="wide")

# Auto-refresh
st.markdown(f"""
<script>
setTimeout(function(){{ window.location.reload(); }}, {REFRESH_MINUTES * 60 * 1000});
</script>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────
@st.cache_data(ttl=REFRESH_MINUTES * 60)
def load_nav():
    df = pd.read_excel(NAV_FILE_PATH)
    df.columns = df.columns.str.strip()
    df["DATE"] = pd.to_datetime(df["DATE"])
    df["PORT NAV"] = pd.to_numeric(df["PORT NAV"], errors="coerce")
    return df.sort_values("DATE").dropna().reset_index(drop=True)

@st.cache_data(ttl=REFRESH_MINUTES * 60)
def load_data():
    df = pd.read_excel(DATA_PATH)
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"])
    return df.sort_values("Date").reset_index(drop=True)

# ─────────────────────────────────────────────
# BASE NAV
# ─────────────────────────────────────────────
def get_base_nav(nav_df):
    today = pd.Timestamp.today()
    current_month = today.to_period("M")

    nav_df = nav_df.copy()
    nav_df["YearMonth"] = nav_df["DATE"].dt.to_period("M")

    prev_month = current_month - 1
    prev_data = nav_df[nav_df["YearMonth"] == prev_month]

    if prev_data.empty:
        base_row = nav_df.sort_values("DATE").iloc[-1]
    else:
        base_row = prev_data.sort_values("DATE").iloc[-1]

    return base_row["PORT NAV"], base_row["DATE"]

# ─────────────────────────────────────────────
# NAV CALCULATION (UNCHANGED)
# ─────────────────────────────────────────────
def calculate_nav(df, base_nav):
    all_dates = sorted(df["Date"].unique())
    if not all_dates:
        return base_nav, 0, None, None, None, None

    # Get the absolute last available date in the file
    current_date = all_dates[-1]
    current_sum = df[df["Date"] == current_date]["Buy_Hold_Value"].sum()

    # For MTD comparison, find the start of the current month's data
    today = pd.Timestamp.today().normalize()
    current_month = today.to_period("M")
    
    month_dates = sorted(df[df["Date"].dt.to_period("M") == current_month]["Date"].unique())
    
    if not month_dates or current_date == month_dates[0]:
        # If no data for current month, or we are on the first day of the month
        prev_month = current_month - 1
        prev_dates = sorted(df[df["Date"].dt.to_period("M") == prev_month]["Date"].unique())
        ref_date = prev_dates[-1] if prev_dates else all_dates[0]
    else:
        ref_date = month_dates[0]

    ref_sum = df[df["Date"] == ref_date]["Buy_Hold_Value"].sum()

    if ref_sum == 0 or pd.isna(ref_sum):
        return current_sum, 0, current_date, ref_date, current_sum, ref_sum

    return_pct = ((current_sum - base_nav) / base_nav) * 100
    current_nav = base_nav * (current_sum / base_nav)

    return current_nav, return_pct, current_date, ref_date, current_sum, ref_sum

# =========================================================
# 🔥 BENCHMARK LOGIC
# =========================================================
@st.cache_data(ttl=REFRESH_MINUTES * 60)
def get_benchmark_values():

    symbol = "BSE500"
    td = TD(TD_USERNAME, TD_PASSWORD, live_port=None, historical_api=True)

    today = pd.Timestamp.today().normalize()
    current_month = today.to_period("M")
    prev_month = current_month - 1

    df = None
    try:
        hist = td.get_historic_data(symbol, duration="2 M", bar_size="eod")
        df = pd.DataFrame(hist)
    except Exception:
        df = None

    if df is None or df.empty:
        return None, None, None, None

    # Detect correct price column
    price_col = None
    for col in ["close", "Close", "c", "ltp"]:
        if col in df.columns:
            price_col = col
            break

    if price_col is None:
        return None, None, None, None

    df["date"] = pd.to_datetime(df["time"]).dt.normalize()
    
    # Filter for dates up to today
    all_dates = sorted(df[df["date"] <= today]["date"].unique())
    
    if not all_dates:
        return None, None, None, None

    # Get the absolute last available date
    current_date = all_dates[-1]
    curr_df = df[df["date"] == current_date]
    current_val = curr_df[price_col].iloc[-1]

    # Previous month last
    prev_df = df[df["date"].dt.to_period("M") == prev_month]
    prev_dates = sorted(prev_df["date"].unique())

    if not prev_dates:
        return None, None, None, None

    base_date = prev_dates[-1]
    base_val = prev_df[prev_df["date"] == base_date][price_col].iloc[-1]

    return current_val, base_val, current_date, base_date


def calculate_benchmark():
    current_val, base_val, current_date, base_date = get_benchmark_values()

    if current_val is None or base_val is None or base_val == 0:
        return 0, None, None, None, None

    bm_return = ((current_val - base_val) / base_val) * 100

    return bm_return, current_val, base_val, current_date, base_date

if __name__ == "__main__":
    # =========================================================
    # MAIN APP
    # =========================================================
    # st.title("📊 Live NAV Dashboard — Buy & Hold Method")

    nav_df = load_nav()
    base_nav, base_date = get_base_nav(nav_df)
    data_df = load_data()

    current_nav, return_pct, current_date, ref_date, current_sum, ref_sum = calculate_nav(data_df, base_nav)

    bm_return, bm_curr, bm_base, bm_curr_date, bm_base_date = calculate_benchmark()

    # 🔥 ALPHA CALCULATION
    alpha = return_pct - bm_return

    # ── PORTFOLIO ─────────────────────────────
    st.markdown("### 💼 Portfolio")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("MTD Return", f"{return_pct:+.2f}%")
    c2.metric("Portfolio Value", f"₹ {current_sum:,.2f}")
    c3.metric("Base NAV", f"{base_nav:.2f}")

    # Alpha with interpretation
    alpha_label = "🟢 Outperformance" if alpha > 0 else "🔴 Underperformance" if alpha < 0 else "⚪ Neutral"
    c4.metric("🔥 Alpha", f"{alpha:+.2f}%", delta=alpha_label, delta_color="off")

    # ── BENCHMARK ─────────────────────────────
    st.divider()
    st.markdown("### 📊 Benchmark")

    b1, b2, b3 = st.columns(3)

    b1.metric("Benchmark Return", f"{bm_return:+.2f}%")

    if bm_curr_date:
        b2.metric("Current (T-1)", f"{bm_curr:,.2f}", bm_curr_date.strftime('%d %b %Y'))

    if bm_base_date:
        b3.metric("Base (Prev Month)", f"{bm_base:,.2f}", bm_base_date.strftime('%d %b %Y'))


# =========================================================
# 🔥 EXPORT FUNCTION FOR OTHER FILES (dummy.py)
# =========================================================

# =========================================================
# PATCH for get_live_nav_data() in Dash.py
# Replace your existing get_live_nav_data() with this version.
# The only addition is "current_bm_nav" in the return dict.
# =========================================================

def get_live_nav_data():
    """
    Used by dummy.py / trailing_returns.py
    Returns all required NAV + live data including current_bm_nav.
    """
    nav_df = load_nav()
    base_nav, base_date = get_base_nav(nav_df)
    data_df = load_data()

    current_nav, return_pct, current_date, ref_date, current_sum, ref_sum = calculate_nav(
        data_df, base_nav
    )

    live_table = data_df[data_df["Date"] == current_date].copy()

    bm_return, bm_curr, bm_base, bm_curr_date, bm_base_date = calculate_benchmark()

    # ── Compute current BM NAV (100-base) from live BSE500 price ─────
    # Scale last known BM NAV in file forward using today's raw BSE500 price
    latest_file_row = nav_df.iloc[-1]
    if bm_curr is not None and bm_base is not None and bm_base != 0:
        current_bm_nav = latest_file_row["BM NAV"] * (bm_curr / bm_base)
    else:
        # Fallback: derive from bm_return (% change from MTD base)
        # bm_return is MTD %, current_bm_nav = last file BM NAV * (1 + bm_return/100)
        current_bm_nav = latest_file_row["BM NAV"] * (1 + (bm_return or 0) / 100)

    return {
        "nav_df":         nav_df,
        "live_table":     live_table,
        "current_nav":    current_nav,       # live PORT NAV (100-base)
        "current_bm_nav": current_bm_nav,    # live BM NAV  (100-base)  ← NEW
        "return":         return_pct,
        "bm_return":      bm_return,
    }