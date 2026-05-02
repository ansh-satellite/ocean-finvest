import os
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from Dash import get_live_nav_data
from nav_updater import compute_calendar_returns

# ─────────────────────────────────────────────
# Credentials & Paths
# ─────────────────────────────────────────────
TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

# Use relative paths for portability
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "MOMENTUM_DB_2 copy", "Trials", "Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx")
DATA_PATH_Final = os.path.join(BASE_DIR,"Momentum_Maxfolio.xlsx")
SECTOR_ALLOCATION_PATH = os.path.join(BASE_DIR, "Sectorwise_equity_allocation.xlsx")
ASSET_ALLOCATION_PATH = os.path.join(BASE_DIR, "stocks_with_sectors.xlsx")
MCAP_ALLOCATION_PATH = os.path.join(BASE_DIR, "mcap_wise_stock_allocation.xlsx")
MONTHLY_DATA_PATH = os.path.join(BASE_DIR, "april_stocks.xlsx")
BENCHMARK_REFRESH_MINUTES = 15

# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Ocean Finvest | Momentum Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# Premium CSS Styling
# ─────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;800&display=swap');

    .stApp {
        background-color: #0b0e14;
        background-image: radial-gradient(circle at 20% 20%, #1a1f2c 0%, #0b0e14 100%);
        font-family: 'Inter', sans-serif;
    }

    [data-testid="stSidebar"] {
        background-color: rgba(15, 20, 28, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.05);
        min-width: 80px !important;
        max-width: 250px !important;
    }

    .glass-card {
        background: rgba(255, 255, 255, 0.03);
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 24px;
        margin-bottom: 24px;
        backdrop-filter: blur(10px);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.37);
        transition: transform 0.3s ease, border 0.3s ease;
    }
    .glass-card:hover {
        transform: translateY(-5px);
        border: 1px solid rgba(0, 230, 118, 0.3);
    }

    .metric-title {
        color: #8892b0;
        font-size: 0.9rem;
        font-weight: 600;
        margin-bottom: 8px;
    }
    .metric-value {
        color: #e6edf3;
        font-size: 1.8rem;
        font-weight: 800;
    }
    .metric-delta {
        font-size: 0.9rem;
        font-weight: 700;
        margin-top: 4px;
    }

    .main-header {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #fff 0%, #8892b0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 30px;
    }

    .custom-table {
        width: 100%;
        border-collapse: separate;
        border-spacing: 0 8px;
    }
    .custom-table th {
        color: #8892b0;
        font-weight: 600;
        text-align: left;
        padding: 12px 16px;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .custom-table td {
        background: rgba(255, 255, 255, 0.02);
        padding: 14px 16px;
        color: #e6edf3;
        font-size: 0.95rem;
        border-top: 1px solid rgba(255, 255, 255, 0.03);
        border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    }
    .custom-table tr td:first-child {
        border-left: 1px solid rgba(255, 255, 255, 0.03);
        border-radius: 10px 0 0 10px;
    }
    .custom-table tr td:last-child {
        border-right: 1px solid rgba(255, 255, 255, 0.03);
        border-radius: 0 10px 10px 0;
    }

    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg, #00e676 0%, #00b0ff 100%);
        color: #0b0e14 !important;
        font-weight: 700;
        border: none;
        border-radius: 12px;
        padding: 10px 24px;
        transition: all 0.3s ease;
    }
    div[data-testid="stButton"] > button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 20px rgba(0, 230, 118, 0.4);
    }

    h1,h2,h3,h4,label { color: #e6edf3 !important; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# Logic Functions
# ─────────────────────────────────────────────
def normalize_ticker_key(series):
    return (
        series.astype(str)
        .str.upper()
        .str.strip()
        .str.replace(".NS", "", regex=False)
        .str.replace("-EQ", "", regex=False)
    )


def normalize_percent_points(series):
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if not numeric.empty and numeric.max() <= 1.0:
        return numeric * 100
    return numeric


def colour_pct_val(val):
    c = "#00e676" if val >= 0 else "#ff5252"
    sign = "+" if val >= 0 else ""
    return f'<span style="color:{c};font-weight:700;">{sign}{val:.2f}%</span>'


def style_alpha(val):
    if pd.isna(val):
        return ""
    color = "#00e676" if val > 0 else "#ff5252" if val < 0 else ""
    return f"color: {color}"


def fmt_inr(val):
    return f"₹ {val:,.2f}" if pd.notnull(val) else "—"


@st.cache_data
def load_and_process_data(file_path):
    if not os.path.exists(file_path):
        return None, None, None, None

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Ticker", "Date"])
    dataset_max_date = df["Date"].max()

    trades = (
        df.groupby(["Ticker"])
        .agg(
            Entry_Date=("Date", "min"),
            Last_Date=("Date", "max"),
            Entry_Price=("Close", "first"),
            Current_Value=("Buy_Hold_Value", "last"),
            Buy_Hold_Value_Start=("Buy_Hold_Value", "first"),
            Buy_Hold_Value_End=("Buy_Hold_Value", "last"),
        )
        .reset_index()
    )
    trades["Return_Abs"] = trades["Buy_Hold_Value_End"] - trades["Buy_Hold_Value_Start"]
    latest_per_ticker = df.groupby("Ticker")["Date"].max().reset_index()
    trades = trades.merge(latest_per_ticker, on="Ticker", suffixes=("", "_Latest"))
    latest_portfolio_date = df["Date"].max()

    active_tickers = df[df["Date"] == latest_portfolio_date]["Ticker"].unique()

# include GoldBees latest available even if it missed today
    gold_tickers = (
    df[df["Ticker"].str.upper().str.contains("GOLDBEES", na=False)]
    .groupby("Ticker")
    .tail(1)["Ticker"]
    .unique()
)

    active_tickers = list(set(active_tickers).union(set(gold_tickers)))

    trades["Is_Active"] = trades["Ticker"].isin(active_tickers)

    pieces = [grp.tail(3) for _, grp in df.groupby("Ticker")]
    daily_snapshot = pd.concat(pieces, ignore_index=True)
    return trades, dataset_max_date, df, daily_snapshot


def build_daily_table(active_holdings, price_history_df):
    rows = []
    maxfolio_path = os.path.join(BASE_DIR, "Momentum_Maxfolio.xlsx")
    maxfolio_df = None
    if os.path.exists(maxfolio_path):
        try:
            maxfolio_df = pd.read_excel(maxfolio_path)
            maxfolio_df["Date"] = pd.to_datetime(maxfolio_df["Date"])
            maxfolio_df["Ticker_Key"] = normalize_ticker_key(maxfolio_df["Ticker"])
        except:
            pass

    today = pd.Timestamp.today().normalize()

    for _, row in active_holdings.iterrows():
        ticker = row["Ticker"]
        ticker_key = normalize_ticker_key(pd.Series([ticker]))[0]

        # ── PRIMARY: Use Momentum_Maxfolio for ALL tickers ──────────────
        source_df = None
        if maxfolio_df is not None:
            source_df = maxfolio_df[maxfolio_df["Ticker_Key"] == ticker_key].sort_values("Date")

        # ── FALLBACK: Use raw price history if not found in maxfolio ────
        if source_df is None or source_df.empty:
            source_df = price_history_df[
                price_history_df["Ticker"] == ticker
            ].sort_values("Date").copy()
            source_df["Date"] = pd.to_datetime(source_df["Date"])

        if source_df is None or source_df.empty:
            continue

        available_dates = sorted(source_df["Date"].dt.normalize().unique())
        
        if not available_dates:
            continue

        # ── Determine Today and Yesterday dates ─────────────────────────
        if today in available_dates:
            today_idx = available_dates.index(today)
            today_dt = today
            # If today is the first date, yesterday is also today
            yesterday_dt = available_dates[today_idx - 1] if today_idx > 0 else today
        else:
            # Last available is "Today", second-to-last is "Yesterday"
            today_dt = available_dates[-1]
            yesterday_dt = available_dates[-2] if len(available_dates) > 1 else available_dates[-1]

        # Get the actual data rows
        today_snap = source_df[source_df["Date"].dt.normalize() == today_dt]
        yest_snap  = source_df[source_df["Date"].dt.normalize() == yesterday_dt]

        if today_snap.empty or yest_snap.empty:
            continue

        t_row = today_snap.iloc[-1]
        y_row = yest_snap.iloc[-1]

        y_close = float(y_row["Close"])
        y_val   = float(y_row["Buy_Hold_Value"])
        t_close = float(t_row["Close"])
        t_val   = float(t_row["Buy_Hold_Value"]) # Use the actual value from the file for "today"

        # Calculate % Change from Yesterday Close to Today Close
        change_pct = ((t_close - y_close) / y_close * 100) if y_close != 0 else 0.0

        rows.append({
            "Ticker":              ticker,
            "Yesterday Buy/Hold":  y_val,
            "Yesterday Close":     y_close,
            "Current Price":       t_close,
            "Ref_Close":           t_close,    # Reference for live refresh
            "Ref_Val":             t_val,      # Reference for live refresh
            "% Change":            round(change_pct, 2),
            "Current Value":       t_val,
        })

    return pd.DataFrame(rows)

def build_daily_contribution_table(daily_table):
    if daily_table is None or daily_table.empty:
        return None

    df = daily_table.copy()
    df["Ticker_Key"] = normalize_ticker_key(df["Ticker"])
    
    equity_df = df[~df["Ticker_Key"].isin(["GOLDBEES", "GOLDBESS", "LIQUIDCASE"])]
    gold_df = df[df["Ticker_Key"].isin(["GOLDBEES", "GOLDBESS"])]
    liquid_df = df[df["Ticker_Key"].isin(["LIQUIDCASE"])]

    equity_return = equity_df["% Change"].mean() if not equity_df.empty else 0.0
    gold_return = gold_df["% Change"].mean() if not gold_df.empty else 0.0
    liquid_return = liquid_df["% Change"].mean() if not liquid_df.empty else 0.0

    out = pd.DataFrame(
        {
            "Particular": ["Equity", "Gold", "Liquidcase"],
            "Weight": [75.0, 10.0, 15.0],
            "Return": [equity_return, gold_return, liquid_return],
        }
    )
    out["Contribution"] = (out["Weight"] * out["Return"]) / 100.0

    total_contrib = out["Contribution"].sum()
    total_row = pd.DataFrame(
        [
            {
                "Particular": "Total",
                "Weight": out["Weight"].sum(),
                "Return": total_contrib,
                "Contribution": total_contrib,
            }
        ]
    )
    return pd.concat([out, total_row], ignore_index=True)


def pick_best_live_column(df, candidate_columns):
    normalized_map = {col.strip().lower(): col for col in df.columns}
    available = [normalized_map[c.lower()] for c in candidate_columns if c.lower() in normalized_map]
    if not available:
        return None
    return max(available, key=lambda c: df[c].notna().sum())


@st.cache_data
def load_sector_allocation(file_path):
    if not os.path.exists(file_path):
        return None
    src = pd.read_excel(file_path)
    sec_col = pick_best_live_column(src, ["SECTOR", "Sector", "Industry"])
    alc_col = pick_best_live_column(src, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    if not sec_col or not alc_col:
        return None
    out = src[[sec_col, alc_col]].copy()
    out.columns = ["Sector", "Percent_Allocation"]
    out["Percent_Allocation"] = normalize_percent_points(out["Percent_Allocation"])
    return out.groupby("Sector", as_index=False)["Percent_Allocation"].sum().sort_values("Percent_Allocation", ascending=False)


@st.cache_data
def load_asset_breakdown(file_path):
    if not os.path.exists(file_path):
        return None
    src = pd.read_excel(file_path)
    ast_col = pick_best_live_column(src, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
    alc_col = pick_best_live_column(src, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    cmp_col = pick_best_live_column(src, ["STOCKS", "Ticker", "Symbol", "SECTOR", "Sector", "Name"])
    if not ast_col or not alc_col or not cmp_col:
        return None
    out = src[[ast_col, cmp_col, alc_col]].copy()
    out.columns = ["Asset_Type", "Component", "Percent_Allocation"]
    out["Percent_Allocation"] = normalize_percent_points(out["Percent_Allocation"])
    return out.groupby(["Asset_Type", "Component"], as_index=False)["Percent_Allocation"].sum()


def apply_target_asset_weights(asset_breakdown_df):
    if asset_breakdown_df is None or asset_breakdown_df.empty:
        return asset_breakdown_df

    weighted = asset_breakdown_df.copy()
    weighted["Asset_Key"] = weighted["Asset_Type"].astype(str).str.upper().str.strip()
    target_map = {"EQUITY": 75.0, "GOLD": 10.0, "LIQUIDCASE": 15.0, "LIQUID": 15.0}
    parts = []

    for ak, grp in weighted.groupby("Asset_Key"):
        grp = grp.copy()
        target = target_map.get(ak, grp["Percent_Allocation"].sum())
        grp["Percent_Allocation"] = target / len(grp) if len(grp) > 0 else 0
        parts.append(grp)

    return pd.concat(parts, ignore_index=True).drop(columns=["Asset_Key"])


@st.cache_data
def load_mcap_allocation(file_path):
    if not os.path.exists(file_path):
        return None
    src = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
    mcap_col = pick_best_live_column(src, ["MCAP", "Mcap", "Market Cap", "Market_Cap"])
    if not mcap_col:
        return None
    out = src[[mcap_col]].copy()
    out.columns = ["Market_Cap"]
    out["Market_Cap"] = out["Market_Cap"].fillna("Unknown").astype(str).str.strip()
    out = out.groupby("Market_Cap", as_index=False).size().rename(columns={"size": "Stock_Count"})
    total = out["Stock_Count"].sum()
    out["Allocation_Pct"] = np.where(total > 0, (out["Stock_Count"] / total) * 100, 0)
    return out.sort_values("Stock_Count", ascending=False)


def fetch_current_nav_values_from_df(nav_df):
    if nav_df.empty:
        return 100.0, 100.0, pd.Timestamp.today().normalize()
    
    today = pd.Timestamp.today().normalize()
    today_data = nav_df[nav_df["DATE"].dt.normalize() == today]
    
    if not today_data.empty:
        row = today_data.iloc[-1]
    else:
        past_data = nav_df[nav_df["DATE"].dt.normalize() <= today]
        if not past_data.empty:
            row = past_data.iloc[-1]
        else:
            row = nav_df.iloc[-1]
            
    return float(row["PORT NAV"]), float(row["BM NAV"]), row["DATE"]


def calculate_trailing_return(nav_df, days, current_nav, current_bm_nav, current_date):
    if pd.isna(current_date):
        return None
    target_date = current_date - pd.Timedelta(days=days)
    historical_rows = nav_df[nav_df["DATE"] <= target_date]
    if historical_rows.empty:
        return None

    selected_row = historical_rows.iloc[-1]
    historical_port_nav = float(selected_row["PORT NAV"])
    historical_bm_nav = float(selected_row["BM NAV"])
    if historical_port_nav == 0 or historical_bm_nav == 0:
        return None

    portfolio_return = ((current_nav - historical_port_nav) / historical_port_nav) * 100
    benchmark_return = ((current_bm_nav - historical_bm_nav) / historical_bm_nav) * 100
    start_date = selected_row["DATE"]
    
    return {
        "Period": f"{days}D" if days != 90 else "3M",
        "Start Date": start_date.strftime("%d-%b-%y") if pd.notna(start_date) else "—",
        "End Date": current_date.strftime("%d-%b-%y"),
        "Portfolio Return": round(portfolio_return, 2),
        "Benchmark Return": round(benchmark_return, 2),
        "Alpha": round(portfolio_return - benchmark_return, 2),
    }


def calculate_since_inception(nav_df, current_nav, current_bm_nav, current_date):
    start_date = "—"
    end_date_str = "—"
    if pd.notna(current_date):
        end_date_str = current_date.strftime("%d-%b-%y")
    if not nav_df.empty:
        first_row = nav_df.iloc[0]
        st_dt = first_row["DATE"]
        if pd.notna(st_dt):
            start_date = st_dt.strftime("%d-%b-%y")
            
    return {
        "Period": "Since Inception",
        "Start Date": start_date,
        "End Date": end_date_str,
        "Portfolio Return": round(current_nav - 100, 2),
        "Benchmark Return": round(current_bm_nav - 100, 2),
        "Alpha": round((current_nav - 100) - (current_bm_nav - 100), 2),
    }


def fetch_ltp_truedata(ticker_list: list) -> dict:
    ltp_map = {}

    try:
        from truedata_ws.websocket.TD import TD
    except ImportError:
        st.error("❌ `truedata-ws` not installed.")
        return {}

    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)

        progress = st.progress(0, text="Fetching latest prices...")
        total = len(ticker_list)

        for i, ticker in enumerate(ticker_list):
            try:
                ticker = ticker.upper()

                # ✅ STEP 1: Get latest tick (LTP)
                tick_data = td.get_n_historical_bars(
                    ticker, no_of_bars=1, bar_size="tick"
                )

                ltp = None
                if tick_data:
                    last_tick = tick_data[-1]
                    ltp = (
                        last_tick.get("ltp")
                        or last_tick.get("close")
                        or last_tick.get("Close")
                    )

                # ❗ FALLBACK (VERY IMPORTANT)
                # If tick fails → use latest intraday/EOD
                if ltp is None:
                    eod_data = td.get_n_historical_bars(
                        ticker, no_of_bars=1, bar_size="EOD"
                    )
                    if eod_data:
                        ltp = eod_data[-1].get("close")

                if ltp is not None:
                    ltp_map[ticker] = float(ltp)

            except Exception:
                continue

            progress.progress((i + 1) / total)

        progress.empty()

    except Exception as e:
        st.error(f"❌ TrueData connection error: {e}")

    finally:
        try:
            if td:
                td.disconnect()
        except:
            pass

    return ltp_map


def build_monthly_performance(file_path):
    if not os.path.exists(file_path):
        return None

    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    ticker_col = df.columns[0]
    start_price_col = df.columns[1]

    df[ticker_col] = (
        df[ticker_col]
        .astype(str)
        .str.upper()
        .str.strip()
        .str.replace(".NS", "", regex=False)
        .str.replace("-EQ", "", regex=False)
    )

    tickers = df[ticker_col].tolist()
    live_prices = fetch_ltp_truedata(tickers)
    df["Current Price"] = df[ticker_col].map(live_prices)
    df["Return %"] = ((df["Current Price"] - df[start_price_col]) / df[start_price_col]) * 100
    df[start_price_col] = pd.to_numeric(df[start_price_col], errors="coerce").round(2)
    df["Current Price"] = pd.to_numeric(df["Current Price"], errors="coerce").round(2)
    df["Return %"] = pd.to_numeric(df["Return %"], errors="coerce").round(2)
    return df


def build_monthly_asset_contribution_table(df):
    if df is None or df.empty:
        return None

    ticker_col = df.columns[0]
    equity_df = df[~df[ticker_col].isin(["GOLDBEES", "LIQUIDCASE"])]
    gold_df = df[df[ticker_col] == "GOLDBEES"]
    liquid_df = df[df[ticker_col] == "LIQUIDCASE"]

    equity_return = equity_df["Return %"].mean() if not equity_df.empty else 0
    gold_return = gold_df["Return %"].mean() if not gold_df.empty else 0
    liquid_return = liquid_df["Return %"].mean() if not liquid_df.empty else 0

    asset_df = pd.DataFrame(
        {
            "Particular": ["Equity", "Gold", "Liquidcase"],
            "Weight": [75.00, 10.00, 15.00],
            "% Returns": [round(equity_return, 2), round(gold_return, 2), round(liquid_return, 2)],
        }
    )
    asset_df["Contribution"] = ((asset_df["Weight"] * asset_df["% Returns"]) / 100).round(2)

    total_row = pd.DataFrame(
        {
            "Particular": ["Total"],
            "Weight": [asset_df["Weight"].sum()],
            "% Returns": [asset_df["Contribution"].sum()],
            "Contribution": [asset_df["Contribution"].sum()],
        }
    )
    return pd.concat([asset_df, total_row], ignore_index=True)


def fetch_benchmark_return_truedata() -> dict:
    result = {
        "change_pct": 0.0,
        "prev_close": 0.0,
        "curr_close": 0.0,
        "bar_time": "—",
        "symbol": "—",
        "error": None,
        "fetched_at": datetime.now().strftime("%d %b %Y  %H:%M:%S"),
    }

    try:
        from truedata_ws.websocket.TD import TD
    except ImportError:
        result["error"] = "truedata-ws not installed"
        return result

    symbols_to_try = ["BSE500", "SPBSE500", "BSE 500", "BSE-500", "CNX500", "NIFTY500", "Nifty 500"]

    def _float(v):
        try:
            return float(v) if v is not None else None
        except Exception:
            return None

    def _close(row):
        for k in ["close", "Close", "c", "C", "ltp"]:
            if isinstance(row, dict) and k in row and row[k] is not None:
                return _float(row[k])
        return None

    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)
        for sym in symbols_to_try:
            try:
                tick = td.get_n_historical_bars(sym, no_of_bars=1, bar_size="EOD")
                eod = td.get_n_historical_bars(sym, no_of_bars=2, bar_size="EOD")
                curr_price = _close(tick[-1]) if tick else None

                if eod and curr_price:
                    prev = _close(eod[-1])
                    if prev and prev > 0:
                        result.update(
                            {
                                "change_pct": round(((curr_price - prev) / prev) * 100, 4),
                                "prev_close": round(prev, 2),
                                "curr_close": round(curr_price, 2),
                                "symbol": sym,
                                "error": None,
                            }
                        )
                        return result
                elif eod and len(eod) >= 2:
                    prev, curr = _close(eod[-2]), _close(eod[-1])
                    if prev and curr and prev > 0:
                        result.update(
                            {
                                "change_pct": round(((curr - prev) / prev) * 100, 4),
                                "prev_close": round(prev, 2),
                                "curr_close": round(curr, 2),
                                "symbol": sym,
                                "error": None,
                            }
                        )
                        return result
            except Exception as e:
                result["error"] = str(e)
                continue
    except Exception as e:
        result["error"] = f"TrueData connection error: {e}"
    finally:
        try:
            if td:
                td.disconnect()
        except Exception:
            pass

    return result


def benchmark_refresh_due() -> bool:
    if "benchmark_data" not in st.session_state:
        return True
    last_fetch = st.session_state.get("benchmark_last_fetched")
    return last_fetch is None or datetime.now() - last_fetch >= timedelta(minutes=BENCHMARK_REFRESH_MINUTES)


def refresh_benchmark_if_due(force: bool = False):
    if force or benchmark_refresh_due():
        with st.spinner("Fetching BSE 500 benchmark..."):
            st.session_state.benchmark_data = fetch_benchmark_return_truedata()
            st.session_state.benchmark_last_fetched = datetime.now()


def compute_portfolio_return_from_table(daily_table) -> float:
    contrib_df = build_daily_contribution_table(daily_table)
    if contrib_df is None or contrib_df.empty:
        return 0.0
    return float(contrib_df.iloc[-1]["Contribution"])


def update_daily_table_with_ltp(active_holdings, ltp_map):
    updated = st.session_state.daily_table.copy()
    for idx, row in updated.iterrows():
        ticker = str(row["Ticker"]).upper()
        ltp = ltp_map.get(ticker)
        if ltp is not None:
            # We compare Live Price vs the "Today" price from the static table
            ref_close = row.get("Ref_Close", row["Current Price"])
            ref_val   = row.get("Ref_Val", row["Current Value"])
            
            # Live change relative to the last close in file
            live_pct = ((ltp - ref_close) / ref_close * 100) if ref_close != 0 else 0.0
            
            # Update Current Price and Current Value
            updated.at[idx, "Current Price"] = ltp
            updated.at[idx, "Current Value"] = round(ref_val * (1 + live_pct / 100), 4)
            
            # The displayed % Change should be the total change from Yesterday (in file) to Live
            yest_close = row["Yesterday Close"]
            total_pct = ((ltp - yest_close) / yest_close * 100) if yest_close != 0 else 0.0
            updated.at[idx, "% Change"] = round(total_pct, 2)

    st.session_state.daily_table = updated
    st.session_state.last_refreshed = datetime.now().strftime("%d %b %Y  %H:%M:%S")
    return updated


# ─────────────────────────────────────────────
# Sidebar Navigation
# ─────────────────────────────────────────────
with st.sidebar:
    st.image("cropped-Untitled-design-scaled-1.webp", use_container_width=True)
    st.markdown("### Momentum Pro")
    st.markdown("---")
    menu = st.radio(
        "Navigation",
        [
            "🏠 Overview",
            "🏭 Allocation",
            "📅 Performance History",
            "📊 Trailing Returns",
            "📆 Monthly Performance",
            "📋 Detailed Tickers",
        ],
        label_visibility="collapsed",
    )
    st.markdown("---")
    if st.button("🔄 Reload Data"):
        st.cache_data.clear()
        if "daily_table" in st.session_state:
            del st.session_state["daily_table"]
        st.rerun()

# ─────────────────────────────────────────────
# Main Data Loading
# ─────────────────────────────────────────────
with st.spinner("Initializing Dashboard..."):
    trades, last_date, raw_df, daily_snapshot = load_and_process_data(DATA_PATH)

    if trades is None:
        st.error(f"Data file not found or could not be loaded: {DATA_PATH}")
        st.stop()

    active_holdings = trades[trades["Is_Active"]].copy()

    if "daily_table" not in st.session_state:
        st.session_state.daily_table = build_daily_table(active_holdings, raw_df)
    if "last_refreshed" not in st.session_state:
        st.session_state.last_refreshed = None

    nav_data = get_live_nav_data()
    nav_df = nav_data["nav_df"]
    live_month_return = nav_data.get("return", 0.0)
    live_month_bm_return = nav_data.get("bm_return", 0.0)

refresh_benchmark_if_due()
bm = st.session_state.benchmark_data
benchmark_ret = bm["change_pct"]
port_ret = compute_portfolio_return_from_table(st.session_state.daily_table)
alpha = port_ret - benchmark_ret

# ─────────────────────────────────────────────
# Header Section
# ─────────────────────────────────────────────
st.markdown("<div class='main-header'>Finance Returns Dashboard</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 🏠 OVERVIEW SECTION
# ─────────────────────────────────────────────
if "Overview" in menu:
    m1, m2, m3 = st.columns(3)

    with m1:
        st.markdown(
            f"""
            <div class='glass-card'>
                <p class='metric-title'>PORTFOLIO RETURN</p>
                <p class='metric-value'>{port_ret:+.2f}%</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f"""
            <div class='glass-card'>
                <p class='metric-title'>BENCHMARK (BSE 500)</p>
                <p class='metric-value'>{benchmark_ret:+.2f}%</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m3:
        alpha_color = "#00e676" if alpha > 0 else "#ff5252" if alpha < 0 else "#e6edf3"
        st.markdown(
            f"""
            <div class='glass-card'>
                <p class='metric-title'>ALPHA GENERATED</p>
                <p style="color:{alpha_color};font-size:1.8rem;font-weight:800;margin:0;">
                    {alpha:+.2f}%
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


    btn_col, ts_col = st.columns([1, 4])
    with btn_col:
        refresh_live_clicked = st.button("🔄 Refresh Live Prices", use_container_width=True)
    with ts_col:
        if st.session_state.last_refreshed:
            st.markdown(
                f"<p style='color:#00e676;margin-top:10px;'>✅ Last live refresh: {st.session_state.last_refreshed}</p>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<p style='color:#888;margin-top:10px;'>Prices from data file. Click Refresh Live Prices for TrueData LTP.</p>",
                unsafe_allow_html=True,
            )

    if refresh_live_clicked:
        ticker_list = active_holdings["Ticker"].str.upper().tolist()
        ltp_map = fetch_ltp_truedata(ticker_list)
        if ltp_map:
            update_daily_table_with_ltp(active_holdings, ltp_map)
            refresh_benchmark_if_due(force=True)
            st.success(f"✅ Live prices updated for {len(ltp_map)} tickers.")
            st.rerun()
        else:
            st.warning("⚠️ No live prices returned. Check credentials or market hours.")

    c1, c2 = st.columns([3, 2])

    with c1:
        st.markdown("<div class='glass-card'><h3>📈 Portfolio Return vs Benchmark</h3>", unsafe_allow_html=True)
        bm_label = "BSE 500 — Daily Change" + (
            f" <span style='font-size:12px;color:#8892b0;'>({bm['bar_time']})</span>"
            if bm.get("bar_time", "—") != "—"
            else ""
        )
        sym_str = bm.get("symbol", "BSE500")
        prev_str = f"₹ {bm['prev_close']:,.2f}" if bm.get("prev_close") else "—"
        curr_str = f"₹ {bm['curr_close']:,.2f}" if bm.get("curr_close") else "—"
        st.markdown(
            f"""
            <table class="custom-table">
              <thead>
                <tr>
                  <th>Metric</th>
                  <th style="text-align:right">Value</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>📈 Portfolio Return</td>
                  <td style="text-align:right">{colour_pct_val(port_ret)}</td>
                </tr>
                <tr>
                  <td>{bm_label}</td>
                  <td style="text-align:right">{colour_pct_val(benchmark_ret)}</td>
                </tr>
                <tr>
                  <td style="font-size:12px;color:#8892b0;">&nbsp;&nbsp;&nbsp;{sym_str}: {prev_str} → {curr_str}</td>
                  <td></td>
                </tr>
                <tr>
                  <td style="font-weight:700;">⚡ Alpha (Portfolio − Benchmark)</td>
                  <td style="text-align:right">{colour_pct_val(alpha)}</td>
                </tr>
              </tbody>
            </table>
            """,
            unsafe_allow_html=True,
        )
        fetched_label = bm.get("fetched_at", "—")
        st.markdown(
            f"<p style='color:#555;font-size:12px;margin-top:10px;'>Benchmark auto-refreshes every {BENCHMARK_REFRESH_MINUTES} mins. Last fetch: {fetched_label}</p>",
            unsafe_allow_html=True,
        )
        if st.button("🔄 Refresh BSE 500 Benchmark", key="refresh_bm_btn"):
            refresh_benchmark_if_due(force=True)
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    with c2:
        st.markdown("<div class='glass-card' style='height: 100%;'><h3>📌 Daily Contribution</h3>", unsafe_allow_html=True)
        contrib_df = build_daily_contribution_table(st.session_state.daily_table)
        if contrib_df is not None:
            contrib_disp = contrib_df.copy()
            contrib_disp["Weight"] = contrib_disp["Weight"].map(lambda x: f"{x:.1f}%")
            contrib_disp["Return"] = contrib_disp["Return"].apply(colour_pct_val)
            contrib_disp["Contribution"] = contrib_disp["Contribution"].apply(colour_pct_val)
            st.write(contrib_disp.to_html(escape=False, index=False, classes="custom-table"), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 🏭 ALLOCATION SECTION
# ─────────────────────────────────────────────
elif "Allocation" in menu:
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<div class='glass-card'><h3>🏭 Sector Allocation</h3>", unsafe_allow_html=True)
        sec_df = load_sector_allocation(SECTOR_ALLOCATION_PATH)
        if sec_df is not None and not sec_df.empty:
            custom_colors = ["#00e676", "#18ffff", "#d500f9", "#ffea00", "#ff5252", "#00b0ff", "#1de9b6", "#ff9100", "#651fff"]
            fig_sec = px.pie(sec_df, names="Sector", values="Percent_Allocation", hole=0.5, color_discrete_sequence=custom_colors)
            fig_sec.update_traces(textposition="inside", textinfo="label+percent", textfont_size=12)
            fig_sec.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#fff"), margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_sec, use_container_width=True)
        else:
            st.info("No sector allocation data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    with col2:
        st.markdown("<div class='glass-card'><h3>🧩 Asset Sunburst</h3>", unsafe_allow_html=True)
        asset_breakdown_df = load_asset_breakdown(ASSET_ALLOCATION_PATH)
        if asset_breakdown_df is not None and not asset_breakdown_df.empty:
            asset_breakdown_df = apply_target_asset_weights(asset_breakdown_df)
            fig_sun = px.sunburst(asset_breakdown_df, path=["Asset_Type", "Component"], values="Percent_Allocation", color_discrete_sequence=px.colors.sequential.Blues)
            fig_sun.update_traces(texttemplate="%{label}<br>%{value:.2f}%", hovertemplate="<b>%{label}</b><br>Allocation: %{value:.2f}%<extra></extra>")
            fig_sun.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#fff"), margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig_sun, use_container_width=True)
        else:
            st.info("No asset breakdown data available.")
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='glass-card'><h3>📊 MCAP Allocation</h3>", unsafe_allow_html=True)
    mcap_df = load_mcap_allocation(MCAP_ALLOCATION_PATH)
    if mcap_df is not None and not mcap_df.empty:
        mcap_colors = ["#ff4081", "#7c4dff", "#00e5ff", "#b2ff59", "#ffd740"]
        fig_mcap = px.pie(mcap_df, names="Market_Cap", values="Allocation_Pct", hole=0.5, color_discrete_sequence=mcap_colors)
        fig_mcap.update_traces(textposition="inside", textinfo="label+percent", textfont_size=14)
        fig_mcap.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#fff"), margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_mcap, use_container_width=True)
    else:
        st.info("No MCAP allocation data available.")
    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📅 PERFORMANCE HISTORY
# ─────────────────────────────────────────────
elif "Performance History" in menu:
    st.markdown("<div class='glass-card'><h3>📅 Calendar Returns</h3>", unsafe_allow_html=True)

    calendar_df = compute_calendar_returns(nav_df)

    # Compute live current NAVs using today's portfolio & benchmark returns
    current_nav, current_bm_nav, _ = fetch_current_nav_values_from_df(nav_df)

    current_month_str = pd.Timestamp.today().strftime("%b-%y")

    # Add current month only if not already present
    if "Month" in calendar_df.columns and current_month_str not in calendar_df["Month"].astype(str).values:

        # Find last NAV before current month started
        month_start = pd.Timestamp.today().replace(day=1)
        prev_month_rows = nav_df[nav_df["DATE"] < month_start]

        if not prev_month_rows.empty:
            month_start_row = prev_month_rows.iloc[-1]

            month_start_port_nav = float(month_start_row["PORT NAV"])
            month_start_bm_nav = float(month_start_row["BM NAV"])

            # Current month return = current live NAV vs month start NAV
            live_month_return = (
                (current_nav - month_start_port_nav) / month_start_port_nav
            ) * 100

            live_month_bm_return = (
                (current_bm_nav - month_start_bm_nav) / month_start_bm_nav
            ) * 100

            live_row = pd.DataFrame(
                [
                    {
                        "Month": current_month_str,
                        "PORT": round(live_month_return, 2),
                        "BSE 500": round(live_month_bm_return, 2),
                        "Alpha": round(
                            live_month_return - live_month_bm_return, 2
                        ),
                    }
                ]
            )

        calendar_df = pd.concat([calendar_df, live_row], ignore_index=True)

    styled_cal = calendar_df.style.format({"PORT": "{:+.2f}%", "BSE 500": "{:+.2f}%", "Alpha": "{:+.2f}%"})
    if "Alpha" in calendar_df.columns:
        styled_cal = styled_cal.map(style_alpha, subset=["Alpha"])
    st.dataframe(styled_cal, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<div class='glass-card'><h3>📈 NAV Performance</h3>", unsafe_allow_html=True)
    if not nav_df.empty:
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=nav_df["DATE"], y=nav_df["PORT NAV"], name="Portfolio", line=dict(color="#00e676", width=3)))
        if "BM NAV" in nav_df.columns:
            fig.add_trace(go.Scatter(x=nav_df["DATE"], y=nav_df["BM NAV"], name="BSE 500", line=dict(color="#ff5252", width=2, dash="dot")))
        fig.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(t=20, l=10, r=10, b=10), hovermode="x unified")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📋 DETAILED TICKERS
# ─────────────────────────────────────────────
elif "Detailed Tickers" in menu:
    st.markdown("<div class='glass-card'><h3>📋 Detailed Ticker Performance</h3>", unsafe_allow_html=True)
    styled = st.session_state.daily_table.copy()
    
    # Reorder and rename columns for better flow
    display_map = {
        "Ticker": "TICKER",
        "Yesterday Buy/Hold": "YESTERDAY VALUE",
        "Yesterday Close": "YESTERDAY CLOSE",
        "Current Price": "CURRENT PRICE",
        "% Change": "% CHANGE",
        "Current Value": "CURRENT VALUE"
    }
    
    # Keep only columns we want to show
    cols_to_show = ["Ticker", "Yesterday Buy/Hold", "Yesterday Close", "Current Price", "% Change", "Current Value"]
    styled = styled[cols_to_show].rename(columns=display_map)

    for col in ["YESTERDAY VALUE", "YESTERDAY CLOSE", "CURRENT PRICE", "CURRENT VALUE"]:
        styled[col] = styled[col].apply(fmt_inr)
    
    styled["% CHANGE"] = styled["% CHANGE"].apply(colour_pct_val)
    
    st.write(styled.to_html(escape=False, index=False, classes="custom-table"), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📊 TRAILING RETURNS
# ─────────────────────────────────────────────
elif "Trailing Returns" in menu:
    st.markdown("<div class='glass-card'><h3>📊 Trailing Returns Snapshot</h3>", unsafe_allow_html=True)
    try:
        current_nav, current_bm_nav, current_date = fetch_current_nav_values_from_df(nav_df)

        nav_col1, nav_col2 = st.columns(2)
        nav_col1.metric("Current Portfolio NAV", f"{current_nav:.2f}")
        nav_col2.metric("Current Benchmark NAV", f"{current_bm_nav:.2f}")

        st.markdown("<br><h4>Trailing Returns</h4>", unsafe_allow_html=True)
        
        end_date_str = current_date.strftime("%d-%b-%y") if pd.notna(current_date) else "—"
        one_day_ago_rows = nav_df[nav_df["DATE"] < current_date]
        one_day_start = one_day_ago_rows.iloc[-1]["DATE"].strftime("%d-%b-%y") if not one_day_ago_rows.empty else "—"

        trailing_results = [
            {
                "Period": "1D",
                "Start Date": one_day_start,
                "End Date": end_date_str,
                "Portfolio Return": round(port_ret, 2),
                "Benchmark Return": round(benchmark_ret, 2),
                "Alpha": round(alpha, 2),
            }
        ]

        for period in [7, 15, 30, 90]:
            result = calculate_trailing_return(nav_df, period, current_nav, current_bm_nav, current_date)
            if result:
                trailing_results.append(result)

        trailing_results.append(calculate_since_inception(nav_df, current_nav, current_bm_nav, current_date))

        trailing_df = pd.DataFrame(trailing_results)
        styled_trail = trailing_df.style.format({"Portfolio Return": "{:+.2f}%", "Benchmark Return": "{:+.2f}%", "Alpha": "{:+.2f}%"})
        if "Alpha" in trailing_df.columns:
            styled_trail = styled_trail.map(style_alpha, subset=["Alpha"])
        st.dataframe(styled_trail, use_container_width=True)
    except Exception as e:
        st.error(f"Error calculating trailing returns: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

# ─────────────────────────────────────────────
# 📆 MONTHLY PERFORMANCE
# ─────────────────────────────────────────────
elif "Monthly Performance" in menu:
    st.markdown("<div class='glass-card'><h3>📆 Monthly Performance Dashboard</h3>", unsafe_allow_html=True)
    if not os.path.exists(MONTHLY_DATA_PATH):
        st.error(f"File not found: {MONTHLY_DATA_PATH}")
    else:
        if st.button("Fetch Monthly Performance"):
            with st.spinner("Fetching Monthly Performance..."):
                result_df = build_monthly_performance(MONTHLY_DATA_PATH)
                if result_df is not None and not result_df.empty:
                    st.success("Performance calculated successfully ✅")
                    st.subheader("Stock Performance Table")
                    styled_stock = result_df.style.format({"Start Price": "{:.2f}", "Current Price": "{:.2f}", "Return %": "{:+.2f}%"})
                    if "Return %" in result_df.columns:
                        styled_stock = styled_stock.map(style_alpha, subset=["Return %"])
                    st.dataframe(styled_stock, use_container_width=True)

                    asset_contrib_df = build_monthly_asset_contribution_table(result_df)
                    if asset_contrib_df is not None:
                        st.subheader("Asset Contribution Table")
                        styled_contrib = asset_contrib_df.style.format({"Weight": "{:.2f}%", "% Returns": "{:+.2f}%", "Contribution": "{:+.2f}%"})
                        if "% Returns" in asset_contrib_df.columns and "Contribution" in asset_contrib_df.columns:
                            styled_contrib = styled_contrib.map(style_alpha, subset=["% Returns", "Contribution"])
                        st.dataframe(styled_contrib, use_container_width=True)
                else:
                    st.error("Could not build monthly performance data.")
    st.markdown("</div>", unsafe_allow_html=True)
