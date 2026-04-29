import os
from datetime import datetime, timedelta, date


import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from truedata_ws.websocket.TD import TD


# ─────────────────────────────────────────────
# TrueData Credentials
# ─────────────────────────────────────────────
TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"


# ─────────────────────────────────────────────
# File Paths
# ─────────────────────────────────────────────
DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"
SECTOR_ALLOCATION_PATH = "Sectorwise_equity_allocation.xlsx"
ASSET_ALLOCATION_PATH = "stocks_with_sectors.xlsx"
MCAP_ALLOCATION_PATH = "mcap_wise_stock_allocation.xlsx"
MONTHLY_DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\april_stocks.xlsx"


BENCHMARK_REFRESH_MINUTES = 15




# ─────────────────────────────────────────────
# Page Config
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="Momentum Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)


st.markdown(
    """
    <style>
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(315deg, #0e1117 0%, #161b22 74%);
    }
    .glassy-container {
        background: rgba(255,255,255,0.05);
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0,0,0,0.1);
        backdrop-filter: blur(5px);
        -webkit-backdrop-filter: blur(5px);
        border: 1px solid rgba(255,255,255,0.1);
        padding: 20px;
        margin-bottom: 20px;
    }
    h1,h2,h3,h4,h5,h6,p,label { color:#e6e6e6 !important; font-family:'Inter',sans-serif; }
    [data-testid="stMetricValue"] { color:#00e676 !important; }
    .dataframe { background-color:transparent !important; color:#e6e6e6 !important; }
    [data-testid="stSidebar"] {
        background-color: rgba(22,27,34,0.95);
        border-right: 1px solid rgba(255,255,255,0.1);
    }
    div[data-testid="stButton"] > button {
        background: linear-gradient(135deg,#00e676 0%,#00bcd4 100%);
        color: #0e1117 !important;
        font-weight: 700;
        border: none;
        border-radius: 10px;
        padding: 0.5rem 1.5rem;
        white-space: normal;
    }
    div[data-testid="stButton"] > button:hover { opacity: 0.85; }
    .benchmark-note {
        color:#888;
        font-size:13px;
        margin-top:6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


components.html(
    f"""
    <script>
    setTimeout(function() {{
        window.parent.location.reload();
    }}, {BENCHMARK_REFRESH_MINUTES * 60 * 1000});
    </script>
    """,
    height=0,
)




# ═══════════════════════════════════════════════════════════
# TRUEDATA LTP FETCHER
# ═══════════════════════════════════════════════════════════
def fetch_ltp_truedata(ticker_list: list) -> dict:
    ltp_map = {}
    try:
        from truedata_ws.websocket.TD import TD
    except ImportError:
        st.error("❌ `truedata-ws` not installed. Run: `pip install truedata-ws`")
        return {}


    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)
        progress = st.progress(0, text="Fetching live prices...")
        total = len(ticker_list)


        for i, ticker in enumerate(ticker_list):
            try:
                data = td.get_n_historical_bars(ticker, no_of_bars=1, bar_size="tick")
                if data and len(data) > 0:
                    last = data[-1]
                    ltp = last.get("ltp") or last.get("close") or last.get("Close")
                    if ltp is not None:
                        ltp_map[ticker.upper()] = float(ltp)
                    else:
                        st.warning(f"⚠️ No LTP key for {ticker}. Keys: {list(last.keys())}")
                else:
                    st.warning(f"⚠️ Empty data for {ticker}")
            except Exception as e:
                st.warning(f"⚠️ Could not fetch {ticker}: {e}")


            progress.progress((i + 1) / total, text=f"Fetched {i + 1}/{total}: {ticker}")


        progress.empty()
    except Exception as e:
        st.error(f"❌ TrueData connection error: {e}")
    finally:
        try:
            if td:
                td.disconnect()
        except Exception:
            pass


    return ltp_map


def fetch_monthly_live_data(ticker_list):
    live_map = {}
    td = None


    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)


        for ticker in ticker_list:
            try:
                tick_bars = td.get_n_historical_bars(
                    ticker,
                    no_of_bars=1,
                    bar_size="tick"
                )


                if tick_bars:
                    ltp = (
                        tick_bars[-1].get("ltp")
                        or tick_bars[-1].get("close")
                        or tick_bars[-1].get("Close")
                    )


                    live_map[ticker.upper()] = ltp


            except Exception:
                pass


    finally:
        if td:
            td.disconnect()


    return live_map




def build_monthly_performance():
    df = pd.read_excel(MONTHLY_DATA_PATH)


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


    live_prices = fetch_monthly_live_data(tickers)


    df["Current Price"] = df[ticker_col].map(live_prices)


    df["Return %"] = (
        (df["Current Price"] - df[start_price_col])
        / df[start_price_col]
    ) * 100


    df[start_price_col] = pd.to_numeric(
        df[start_price_col], errors="coerce"
    ).round(2)


    df["Current Price"] = pd.to_numeric(
        df["Current Price"], errors="coerce"
    ).round(2)


    df["Return %"] = pd.to_numeric(
        df["Return %"], errors="coerce"
    ).round(2)


    return df




def build_monthly_asset_contribution(df):
    df = df.copy()


    ticker_col = df.columns[0]


    gold_ticker = "GOLDBEES"
    liquid_ticker = "LIQUIDCASE"


    equity_df = df[
        ~df[ticker_col].isin([gold_ticker, liquid_ticker])
    ]


    gold_df = df[df[ticker_col] == gold_ticker]


    liquid_df = df[df[ticker_col] == liquid_ticker]


    equity_return = equity_df["Return %"].mean() if not equity_df.empty else 0
    gold_return = gold_df["Return %"].mean() if not gold_df.empty else 0
    liquid_return = liquid_df["Return %"].mean() if not liquid_df.empty else 0


    asset_df = pd.DataFrame({
        "Particular": ["Equity", "Gold", "Liquidcase"],
        "Weight": [75.00, 10.00, 15.00],
        "% Returns": [
            round(equity_return, 2),
            round(gold_return, 2),
            round(liquid_return, 2)
        ]
    })


    asset_df["Contribution"] = (
        asset_df["Weight"] * asset_df["% Returns"]
    ) / 100


    asset_df["Contribution"] = asset_df["Contribution"].round(2)


    total_row = pd.DataFrame({
        "Particular": ["Total"],
        "Weight": [100.00],
        "% Returns": [asset_df["Contribution"].sum()],
        "Contribution": [asset_df["Contribution"].sum()]
    })


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


    symbols_to_try = [
        "BSE500", "SPBSE500", "BSE 500", "BSE-500",
        "S&P BSE 500", "S&P BSE500",
        "CNX500", "CNX 500", "NIFTY500", "NIFTY 500", "Nifty 500",
    ]


    def get_field(row, keys, default=None):
        if row is None:
            return default
        for key in keys:
            if isinstance(row, dict) and key in row and row.get(key) is not None:
                return row.get(key)
            if hasattr(row, key):
                value = getattr(row, key)
                if value is not None:
                    return value
        return default


    def as_float(value):
        try:
            return float(value) if value is not None else None
        except Exception:
            return None


    def close_from_bar(row):
        return as_float(get_field(row, ["close", "Close", "c", "C", "ltp", "LTP"]))


    def time_from_bar(row):
        return str(get_field(row, ["time", "timestamp", "date", "datetime", "t"], "—"))


    def get_latest_tick_price(td, symbol):
        tick_data = td.get_n_historical_bars(symbol, no_of_bars=1, bar_size="tick")
        if not tick_data:
            return None, "—"
        last_tick = tick_data[-1]
        ltp = as_float(get_field(last_tick, ["ltp", "LTP", "close", "Close", "c", "C"]))
        return ltp, time_from_bar(last_tick)


    def get_eod_bars(td, symbol):
        last_error = None
        for bar_size in ["eod", "EOD"]:
            try:
                bars = td.get_n_historical_bars(symbol, no_of_bars=2, bar_size=bar_size)
                if bars and len(bars) >= 1:
                    return bars, None
            except Exception as e:
                last_error = e
        return None, last_error


    attempts = []
    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)


        for sym in symbols_to_try:
            try:
                curr_price, tick_time = get_latest_tick_price(td, sym)
                eod_bars, eod_error = get_eod_bars(td, sym)


                if eod_bars and curr_price:
                    prev_close = close_from_bar(eod_bars[-1])
                    curr_close = curr_price
                    bar_time = tick_time
                elif eod_bars and len(eod_bars) >= 2:
                    prev_close = close_from_bar(eod_bars[-2])
                    curr_close = close_from_bar(eod_bars[-1])
                    bar_time = time_from_bar(eod_bars[-1])
                else:
                    attempts.append(f"{sym}: tick={curr_price}, eod_error={eod_error or 'no EOD bars'}")
                    continue


                if not prev_close or not curr_close or prev_close <= 0:
                    attempts.append(f"{sym}: invalid prices prev={prev_close}, current={curr_close}")
                    continue


                change_pct = ((curr_close - prev_close) / prev_close) * 100
                result.update(
                    {
                        "change_pct": round(change_pct, 4),
                        "prev_close": round(prev_close, 2),
                        "curr_close": round(curr_close, 2),
                        "bar_time": bar_time,
                        "symbol": sym,
                        "error": None,
                        "fetched_at": datetime.now().strftime("%d %b %Y  %H:%M:%S"),
                    }
                )
                return result


            except Exception as e:
                result["error"] = f"{sym}: {e}"
                attempts.append(f"{sym}: {e}")
                continue


    except Exception as e:
        result["error"] = f"TrueData connection error: {e}"
    finally:
        try:
            if td:
                td.disconnect()
        except Exception:
            pass


    if attempts:
        result["error"] = " | ".join(attempts[-5:])
    return result




def benchmark_refresh_due() -> bool:
    if "benchmark_data" not in st.session_state:
        return True
    last_fetch = st.session_state.get("benchmark_last_fetched")
    if last_fetch is None:
        return True
    return datetime.now() - last_fetch >= timedelta(minutes=BENCHMARK_REFRESH_MINUTES)




def refresh_benchmark_if_due(force: bool = False):
    if force or benchmark_refresh_due():
        with st.spinner("Fetching BSE 500 daily benchmark..."):
            st.session_state.benchmark_data = fetch_benchmark_return_truedata()
            st.session_state.benchmark_last_fetched = datetime.now()






# ═══════════════════════════════════════════════════════════
# HELPER UTILITIES
# ═══════════════════════════════════════════════════════════
def pick_best_live_column(df, candidate_columns):
    normalized_map = {col.strip().lower(): col for col in df.columns}
    available = []
    for candidate in candidate_columns:
        match = normalized_map.get(candidate.lower())
        if match:
            available.append(match)
    if not available:
        return None


    def filled_count(col_name):
        series = df[col_name]
        if series.dtype == "object":
            return series.fillna("").astype(str).str.strip().ne("").sum()
        return series.notna().sum()


    return max(available, key=filled_count)




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
    if numeric.empty:
        return numeric
    if numeric.max() <= 1.0:
        return numeric * 100
    return numeric




def fmt_inr(val):
    try:
        f = float(val)
        return f"₹ {f:,.2f}" if not np.isnan(f) else "—"
    except Exception:
        return "—"




def colour_pct(val):
    try:
        # Strip '%' if present for conversion
        clean_val = str(val).replace("%", "").strip()
        v = float(clean_val)
        c = "#00e676" if v >= 0 else "#ff5252"
        # If it was originally a percentage string, keep the % in output
        suffix = "%" if "%" in str(val) else ""
        return f'<span style="color:{c};font-weight:700;">{v:+.2f}{suffix}</span>'
    except Exception:
        return str(val)




def colour_pct_val(val):
    try:
        v = float(val)
        c = "#00e676" if v >= 0 else "#ff5252"
        sign = "+" if v >= 0 else ""
        return f'<span style="color:{c};font-weight:700;">{sign}{v:.2f}%</span>'
    except Exception:
        return "—"




def pie_layout():
    return dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#e6e6e6"),
        margin=dict(t=10, l=10, r=10, b=10),
    )




# ═══════════════════════════════════════════════════════════
# DATA LOADERS
# ═══════════════════════════════════════════════════════════
@st.cache_data
def load_and_process_data(file_path):
    if not os.path.exists(file_path):
        return None, None, None, None


    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Ticker", "Date"])
    df["YearMonth"] = df["Date"].dt.to_period("M")


    if "Quantity" not in df.columns:
        if "Close" in df.columns and "Buy_Hold_Value" in df.columns:
            df["Quantity"] = (df["Buy_Hold_Value"] / df["Close"]).round(4)
        else:
            df["Quantity"] = 1


    df_month = df.drop_duplicates(subset=["Ticker", "YearMonth"]).sort_values(["Ticker", "YearMonth"])


    def get_trade_id(g):
        diff_months = g["YearMonth"].diff().apply(lambda x: x.n if pd.notna(x) else 1)
        qty = g["Quantity"]
        new_trade = diff_months.isna() | (diff_months > 1) | (qty != qty.shift(1))
        return new_trade.cumsum()


    df_month["trade_id"] = df_month.groupby("Ticker", group_keys=False).apply(get_trade_id)
    df = df.merge(df_month[["Ticker", "YearMonth", "trade_id"]], on=["Ticker", "YearMonth"], how="left")


    dataset_max_date = df["Date"].max()


    trades = df.groupby(["Ticker", "trade_id"]).agg(
        Entry_Date=("Date", "min"),
        Last_Date=("Date", "max"),
        Entry_Price=("Close", "first"),
        Current_Value=("Buy_Hold_Value", "last"),
        Quantity=("Quantity", "last"),
        Buy_Hold_Value_Start=("Buy_Hold_Value", "first"),
        Buy_Hold_Value_End=("Buy_Hold_Value", "last"),
    ).reset_index()


    trades["Return_Abs"] = trades["Buy_Hold_Value_End"] - trades["Buy_Hold_Value_Start"]
    trades["Return_Pct"] = (trades["Buy_Hold_Value_End"] / trades["Buy_Hold_Value_Start"]) - 1
    
    # Always consider Gold and Liquidcase active even if their data in the file is stale
    permanent_assets = ["GOLDBEES", "GOLDBESS", "LIQUIDCASE"]
    is_latest_date = trades["Last_Date"] == dataset_max_date
    is_permanent = trades["Ticker"].str.upper().str.strip().isin(permanent_assets)
    trades["Is_Active"] = is_latest_date | is_permanent


    pieces = []
    for _, grp in df.sort_values(["Ticker", "Date"]).groupby("Ticker", sort=False):
        pieces.append(grp.tail(2))
    daily_snapshot = pd.concat(pieces, ignore_index=True)


    return trades, dataset_max_date, df, daily_snapshot




@st.cache_data
def load_portfolio_daily_comparison(file_path):
    if not os.path.exists(file_path):
        return None, None, None, None, None


    df = pd.read_excel(file_path)
    df.columns = df.columns.str.strip()
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Ticker", "Date"])


    dates = sorted(df["Date"].dropna().unique())
    if not dates:
        return None, None, None, None, None


    current_date = dates[-1]
    yesterday_date = dates[-2] if len(dates) >= 2 else current_date


    df_cur = df[df["Date"] == current_date].copy()
    df_prev = df[df["Date"] == yesterday_date].copy()


    merged = df_cur[["Ticker", "Close", "Buy_Hold_Value"]].merge(
        df_prev[["Ticker", "Close", "Buy_Hold_Value"]],
        on="Ticker",
        suffixes=("_Current", "_Yesterday"),
        how="left",
    )
    merged["Buy_Hold_Value_Yesterday"] = merged["Buy_Hold_Value_Yesterday"].fillna(0)
    merged["Close_Yesterday"] = merged["Close_Yesterday"].fillna(0)


    merged["Pct_Change"] = np.where(
        merged["Close_Yesterday"] != 0,
        ((merged["Close_Current"] - merged["Close_Yesterday"]) / merged["Close_Yesterday"]) * 100,
        0,
    )


    total_cur = df_cur["Buy_Hold_Value"].sum()
    total_prev = df_prev["Buy_Hold_Value"].sum()
    portfolio_return_pct = ((total_cur - total_prev) / total_prev * 100) if total_prev > 0 else 0.0


    return merged, current_date, yesterday_date, portfolio_return_pct, (total_cur, total_prev)




@st.cache_data
def load_sector_allocation(file_path):
    if not os.path.exists(file_path):
        return None
    src = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
    sector_col = pick_best_live_column(src, ["SECTOR", "Sector", "Industry"])
    allocation_col = pick_best_live_column(src, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    if not sector_col or not allocation_col:
        return None
    out = src[[sector_col, allocation_col]].copy()
    out.columns = ["Sector", "Percent_Allocation"]
    out["Sector"] = out["Sector"].fillna("Unknown").astype(str).str.strip()
    out["Percent_Allocation"] = normalize_percent_points(out["Percent_Allocation"])
    out = out.groupby("Sector", as_index=False)["Percent_Allocation"].sum().sort_values("Percent_Allocation", ascending=False)
    return out[out["Percent_Allocation"] > 0]




@st.cache_data
def load_asset_allocation(primary_path, fallback_path=None):
    def _load(p):
        if not p or not os.path.exists(p):
            return None
        return pd.read_excel(p) if p.endswith(".xlsx") else pd.read_csv(p)


    src = _load(primary_path)
    if src is None:
        src = _load(fallback_path)
    if src is None:
        return None


    asset_col = pick_best_live_column(src, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
    allocation_col = pick_best_live_column(src, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    if asset_col is None or allocation_col is None:
        return None


    out = src[[asset_col, allocation_col]].copy()
    out.columns = ["Asset_Type", "Percent_Allocation"]
    out["Asset_Type"] = out["Asset_Type"].fillna("Unknown").astype(str).str.strip()
    out["Percent_Allocation"] = normalize_percent_points(out["Percent_Allocation"])
    out = out.groupby("Asset_Type", as_index=False)["Percent_Allocation"].sum().sort_values("Percent_Allocation", ascending=False)
    return out[out["Percent_Allocation"] > 0]




@st.cache_data
def load_asset_breakdown(file_path):
    if not os.path.exists(file_path):
        return None
    src = pd.read_excel(file_path) if file_path.endswith(".xlsx") else pd.read_csv(file_path)
    asset_col = pick_best_live_column(src, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
    allocation_col = pick_best_live_column(src, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    component_col = pick_best_live_column(src, ["STOCKS", "Ticker", "Symbol", "SECTOR", "Sector", "Name"])
    if not asset_col or not allocation_col or not component_col:
        return None
    out = src[[asset_col, component_col, allocation_col]].copy()
    out.columns = ["Asset_Type", "Component", "Percent_Allocation"]
    out["Asset_Type"] = out["Asset_Type"].fillna("Unknown").astype(str).str.strip()
    out["Component"] = out["Component"].fillna("Unknown").astype(str).str.strip()
    out["Percent_Allocation"] = normalize_percent_points(out["Percent_Allocation"])
    out = out.groupby(["Asset_Type", "Component"], as_index=False)["Percent_Allocation"].sum()
    out = out.sort_values(["Asset_Type", "Percent_Allocation"], ascending=[True, False])
    return out[out["Percent_Allocation"] > 0]




def apply_target_asset_weights(asset_breakdown_df, asset_allocation_df):
    if asset_breakdown_df is None or asset_breakdown_df.empty:
        return asset_breakdown_df
    weighted = asset_breakdown_df.copy()
    weighted["Asset_Key"] = weighted["Asset_Type"].astype(str).str.upper().str.strip()
    target_map = {}
    if asset_allocation_df is not None and not asset_allocation_df.empty:
        tmp = asset_allocation_df.copy()
        tmp["Asset_Key"] = tmp["Asset_Type"].astype(str).str.upper().str.strip()
        target_map = tmp.groupby("Asset_Key")["Percent_Allocation"].sum().to_dict()
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












# ═══════════════════════════════════════════════════════════
# MTD (TRAILING) RETURNS MODULE
# ═══════════════════════════════════════════════════════════
def compute_mtd_portfolio_return(df: pd.DataFrame):
    if df is None or df.empty:
        return 0.0, None, None


    df = df.copy()
    df["Date"] = pd.to_datetime(df["Date"])


    today = datetime.today()
    month_df = df[(df["Date"].dt.month == today.month) & (df["Date"].dt.year == today.year)].sort_values("Date")


    if month_df.empty:
        return 0.0, None, None


    start_date = month_df["Date"].min()
    latest_date = month_df["Date"].max()
    start_val = df[df["Date"] == start_date]["Buy_Hold_Value"].sum()
    current_val = df[df["Date"] == latest_date]["Buy_Hold_Value"].sum()


    if start_val == 0:
        return 0.0, start_date, latest_date


    mtd_return = ((current_val - start_val) / start_val) * 100
    return round(mtd_return, 4), start_date, latest_date




def compute_mtd_benchmark_return_truedata():
    try:
        from truedata_ws.websocket.TD import TD
    except ImportError:
        return 0.0, "truedata not installed"


    td = None
    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)
        bars = td.get_n_historical_bars("BSE500", no_of_bars=40, bar_size="EOD")


        if not bars:
            return 0.0, "No data"


        df = pd.DataFrame(bars)
        df["date"] = pd.to_datetime(df["date"])


        today = datetime.today()
        month_df = df[(df["date"].dt.month == today.month) & (df["date"].dt.year == today.year)].sort_values("date")


        if len(month_df) < 2:
            return 0.0, "Insufficient data"


        start_close = float(month_df.iloc[0]["close"])
        latest_close = float(month_df.iloc[-1]["close"])


        if start_close == 0:
            return 0.0, "Invalid start"


        ret = ((latest_close - start_close) / start_close) * 100
        return round(ret, 4), None


    except Exception as e:
        return 0.0, str(e)
    finally:
        try:
            if td:
                td.disconnect()
        except Exception:
            pass




def handle_mtd_logic(raw_df):
    if "mtd_locked" not in st.session_state:
        st.session_state.mtd_locked = False
    if "mtd_portfolio" not in st.session_state:
        st.session_state.mtd_portfolio = None
    if "mtd_benchmark" not in st.session_state:
        st.session_state.mtd_benchmark = None


    today = datetime.today()
    latest_data_month = pd.to_datetime(raw_df["Date"]).max().month


    if latest_data_month < today.month:
        st.session_state.mtd_locked = True


    if not st.session_state.mtd_locked:
        mtd_port, _, _ = compute_mtd_portfolio_return(raw_df)
        mtd_bm, _ = compute_mtd_benchmark_return_truedata()
        st.session_state.mtd_portfolio = mtd_port
        st.session_state.mtd_benchmark = mtd_bm
    else:
        mtd_port = st.session_state.mtd_portfolio or 0.0
        mtd_bm = st.session_state.mtd_benchmark or 0.0


    mtd_alpha = mtd_port - mtd_bm
    return mtd_port, mtd_bm, mtd_alpha, st.session_state.mtd_locked




# ═══════════════════════════════════════════════════════════
# ANALYTICS FUNCTIONS
# ═══════════════════════════════════════════════════════════
#november = goldbees


def build_daily_contribution_table(daily_table: pd.DataFrame):
    if daily_table is None or daily_table.empty:
        return None


    required_cols = {"Ticker", "Yesterday Buy/Hold", "Current Value"}
    if not required_cols.issubset(daily_table.columns):
        return None


    df = daily_table.copy()
    df["Ticker_Key"] = normalize_ticker_key(df["Ticker"])
    df["Yesterday Buy/Hold"] = pd.to_numeric(df["Yesterday Buy/Hold"], errors="coerce").fillna(0.0)
    df["Current Value"] = pd.to_numeric(df["Current Value"], errors="coerce").fillna(0.0)


    total_prev_portfolio = df["Yesterday Buy/Hold"].sum()
    if total_prev_portfolio == 0:
        return None


    gold_symbols = {"GOLDBEES", "GOLDBESS"}
    liquid_symbols = {"LIQUIDCASE"}


    df["Category"] = "Equity"
    df.loc[df["Ticker_Key"].isin(gold_symbols), "Category"] = "Gold"
    df.loc[df["Ticker_Key"].isin(liquid_symbols), "Category"] = "Liquidcase"


    grouped = df.groupby("Category").agg({"Yesterday Buy/Hold": "sum", "Current Value": "sum"}).reset_index()
    grouped["Weight"] = (grouped["Yesterday Buy/Hold"] / total_prev_portfolio) * 100
    grouped["Return"] = np.where(
        grouped["Yesterday Buy/Hold"] != 0,
        ((grouped["Current Value"] - grouped["Yesterday Buy/Hold"]) / grouped["Yesterday Buy/Hold"]) * 100,
        0.0,
    )
    grouped["Contribution"] = (grouped["Weight"] * grouped["Return"]) / 100.0


    cat_order = {"Equity": 0, "Gold": 1, "Liquidcase": 2}
    grouped["sort_order"] = grouped["Category"].map(cat_order).fillna(3)
    grouped = grouped.sort_values("sort_order").drop(columns=["sort_order"])


    out = grouped[["Category", "Weight", "Return", "Contribution"]].rename(columns={"Category": "Particular"})
    total_weight = out["Weight"].sum()
    total_contrib = out["Contribution"].sum()
    total_row = pd.DataFrame(
        [{"Particular": "Total", "Weight": total_weight, "Return": total_contrib, "Contribution": total_contrib}]
    )
    return pd.concat([out, total_row], ignore_index=True)




def build_daily_table(active_holdings: pd.DataFrame, daily_snapshot: pd.DataFrame) -> pd.DataFrame:
    today_str = datetime.today().strftime("%Y-%m-%d")
    rows = []


    for _, row in active_holdings.iterrows():
        ticker = row["Ticker"]
        snap = daily_snapshot[daily_snapshot["Ticker"] == ticker].sort_values("Date")


        if len(snap) >= 2:
            yesterday_row = snap.iloc[-2]
            today_row = snap.iloc[-1]
        elif len(snap) == 1:
            yesterday_row = snap.iloc[-1]
            today_row = snap.iloc[-1]
        else:
            continue


        yest_close = float(yesterday_row.get("Close", np.nan))
        yest_value = float(yesterday_row.get("Buy_Hold_Value", np.nan))
        curr_price = float(today_row.get("Close", np.nan))


        pct_change = ((curr_price - yest_close) / yest_close * 100) if pd.notna(yest_close) and yest_close != 0 else 0.0
        current_value = yest_value * (1 + pct_change / 100)


        rows.append(
            {
                "Ticker": ticker,
                "Current Date": today_str,
                "Yesterday Buy/Hold": round(yest_value, 4),
                "Yesterday Close": round(yest_close, 2),
                "Current Price": round(curr_price, 2),
                "% Change": round(pct_change, 2),
                "Current Value": round(current_value, 4),
            }
        )


    return pd.DataFrame(rows)




def compute_portfolio_return_from_table(daily_table: pd.DataFrame) -> float:
    if daily_table is None or daily_table.empty:
        return 0.0
    total_cur = pd.to_numeric(daily_table["Current Value"], errors="coerce").fillna(0).sum()
    total_prev = pd.to_numeric(daily_table["Yesterday Buy/Hold"], errors="coerce").fillna(0).sum()
    if total_prev == 0:
        return 0.0
    return (total_cur - total_prev) / total_prev * 100




def daily_value_totals(daily_table: pd.DataFrame):
    if daily_table is None or daily_table.empty:
        return 0.0, 0.0
    total_prev = pd.to_numeric(daily_table["Yesterday Buy/Hold"], errors="coerce").fillna(0).sum()
    total_cur = pd.to_numeric(daily_table["Current Value"], errors="coerce").fillna(0).sum()
    return total_prev, total_cur




def update_daily_table_with_ltp(active_holdings, ltp_map):
    updated = st.session_state.daily_table.copy()
    for idx, row in updated.iterrows():
        ticker = str(row["Ticker"]).upper()
        ltp = ltp_map.get(ticker)
        if ltp is not None:
            yest_val = row["Yesterday Buy/Hold"]
            yest_close = row["Yesterday Close"]
            pct = ((ltp - yest_close) / yest_close * 100) if pd.notna(yest_close) and yest_close != 0 else 0.0
            new_val = yest_val * (1 + pct / 100)
            updated.at[idx, "Current Value"] = round(new_val, 4)
            updated.at[idx, "Current Price"] = ltp
            updated.at[idx, "% Change"] = round(pct, 2)


    st.session_state.daily_table = updated
    st.session_state.last_refreshed = datetime.now().strftime("%d %b %Y  %H:%M:%S")
    return updated


# =========================================================
# PAGE STATE
# =========================================================
if "show_trailing_returns" not in st.session_state:
    st.session_state.show_trailing_returns = False




# =========================================================
# PAGE ROUTING
# =========================================================
# =========================================================
# PAGE ROUTING
# =========================================================
if st.session_state.show_trailing_returns:


    # Lazy import to avoid circular import
    from trailing_returns import (
        show_trailing_returns_page
    )


    show_trailing_returns_page()


    st.stop()


# ═══════════════════════════════════════════════════════════
# MAIN APP
# ═══════════════════════════════════════════════════════════
st.title("🚀 Momentum Portfolio Dashboard")


if not os.path.exists(DATA_PATH):
    st.error(f"Data file not found at: {DATA_PATH}")
    st.stop()


ref_col, info_col = st.columns([1, 3])
with ref_col:
    if st.button("🔄 Restart / Refresh Data", use_container_width=True):
        st.cache_data.clear()
        for key in [
            "daily_table",
            "last_refreshed",
            "benchmark_data",
            "benchmark_last_fetched",
            "mtd_locked",
            "mtd_portfolio",
            "mtd_benchmark",
        ]:
            if key in st.session_state:
                del st.session_state[key]
        st.rerun()
with info_col:
    st.caption("Clears cached data and reloads from file. Live prices and BSE 500 benchmark can be refreshed below.")


with st.spinner("Processing Data..."):
    trades, last_update_date, raw_df, daily_snapshot = load_and_process_data(DATA_PATH)
    daily_df, current_date, yesterday_date, file_portfolio_return_pct, value_totals = load_portfolio_daily_comparison(DATA_PATH)


if trades is None:
    st.error("Failed to load data.")
    st.stop()


st.caption(
    f"📅 Last File Update: **{last_update_date.strftime('%d %B %Y')}**"
    + (
        f"  |  Tracking: **{pd.to_datetime(current_date).strftime('%d %B %Y')}** "
        f"vs **{pd.to_datetime(yesterday_date).strftime('%d %B %Y')}**"
        if current_date is not None
        else ""
    )
)


sector_allocation_df = load_sector_allocation(SECTOR_ALLOCATION_PATH)
asset_allocation_df = load_asset_allocation(ASSET_ALLOCATION_PATH)
asset_breakdown_df = load_asset_breakdown(ASSET_ALLOCATION_PATH)
asset_breakdown_df = apply_target_asset_weights(asset_breakdown_df, asset_allocation_df)
mcap_allocation_df = load_mcap_allocation(MCAP_ALLOCATION_PATH)


active_holdings = trades[trades["Is_Active"]].copy()
total_return_abs = active_holdings["Return_Abs"].sum()
active_holdings["Contribution_Pct_Total_Return"] = (
    active_holdings["Return_Abs"] / total_return_abs * 100 if total_return_abs != 0 else 0
)


if "daily_table" not in st.session_state:
    st.session_state.daily_table = build_daily_table(active_holdings, daily_snapshot)
    st.session_state.last_refreshed = None


refresh_benchmark_if_due()




# Portfolio Overview Removed as requested




# ════════════════════════════════════════════════════════════
# SECTION 2 — DAILY RETURN / BENCHMARK / ALPHA
# ════════════════════════════════════════════════════════════
st.markdown("## 📈 Daily Return vs Benchmark (BSE 500 — Daily Change)")
st.markdown('<div class="glassy-container">', unsafe_allow_html=True)


col_live_btn, col_month_btn, col_trailing_btn, col_live_ts = st.columns([1,1,1,2])


with col_live_btn:
    refresh_live_clicked = st.button(
        "🔄 Refresh Live Prices",
        use_container_width=True
    )


with col_month_btn:
    monthly_analysis_clicked = st.button(
        "📅 Monthly Analysis",
        use_container_width=True
    )
with col_trailing_btn:
    trailing_analysis_clicked = st.button(
    "📊 Trailing Returns",
    use_container_width=True,
    key="main_trailing_btn"
)


if refresh_live_clicked:
    ticker_list = active_holdings["Ticker"].str.upper().tolist()
    ltp_map = fetch_ltp_truedata(ticker_list)
    if ltp_map:
        update_daily_table_with_ltp(active_holdings, ltp_map)
        refresh_benchmark_if_due(force=True)
        st.success(f"✅ Live prices updated for {len(ltp_map)} tickers.")
    else:
        st.warning("⚠️ No live prices returned. Check credentials or market hours.")


if monthly_analysis_clicked:
    st.markdown("## 📅 Monthly Analysis")


    monthly_df = build_monthly_performance()


    st.subheader("Monthly Stock Performance")


    st.dataframe(
        monthly_df.style.format({
            "Start Price": "{:.2f}",
            "Current Price": "{:.2f}",
            "Return %": "{:+.2f}%"
        }),
        use_container_width=True
    )


    asset_monthly_df = build_monthly_asset_contribution(monthly_df)


    st.subheader("Monthly Asset Contribution")


    st.dataframe(
        asset_monthly_df.style.format({
            "Weight": "{:.2f}%",
            "% Returns": "{:.2f}%",
            "Contribution": "{:.2f}%"
        }),
        use_container_width=True
    )


    st.stop()


if trailing_analysis_clicked:
    st.session_state.show_trailing_returns = True
    st.rerun()


bm = st.session_state.benchmark_data
benchmark_ret = bm["change_pct"]


port_ret = compute_portfolio_return_from_table(
    st.session_state.daily_table
)


total_prev_val, total_cur_val = daily_value_totals(
    st.session_state.daily_table
)


alpha = (
    port_ret - benchmark_ret
)


# =========================================================
# SAVE DAILY VALUES FOR TRAILING RETURNS PAGE
# =========================================================
st.session_state["portfolio_return"] = (
    port_ret
)


st.session_state["benchmark_return"] = (
    benchmark_ret
)


st.session_state["alpha"] = (
    alpha
)


if bm["error"]:
    with st.expander("⚠️ Benchmark fetch details", expanded=False):
        st.warning(f"Symbol tried: **{bm['symbol']}** | Error: {bm['error']}")


# Portfolio Value Metrics Removed as requested


col_b1, col_b2 = st.columns([2, 1])


with col_b1:
    bm_label = "📊 BSE 500 — Daily Change" + (
        f" &nbsp;<span style='font-size:12px;color:#888;'>({bm['bar_time']})</span>" if bm["bar_time"] != "—" else ""
    )
    prev_str = f"₹ {bm['prev_close']:,.2f}" if bm["prev_close"] else "—"
    curr_str = f"₹ {bm['curr_close']:,.2f}" if bm["curr_close"] else "—"
    sym_str = bm["symbol"] if bm["symbol"] != "—" else "BSE500"


    st.markdown(
        f"""
        <table style="width:100%;border-collapse:collapse;color:#e6e6e6;font-size:15px;">
          <thead>
            <tr style="border-bottom:1px solid rgba(255,255,255,0.2);">
              <th style="padding:12px 16px;text-align:left;">Metric</th>
              <th style="padding:12px 16px;text-align:right;">Value</th>
            </tr>
          </thead>
          <tbody>
            <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
              <td style="padding:12px 16px;">📈 Portfolio Change</td>
              <td style="padding:12px 16px;text-align:right;">{colour_pct_val(port_ret)}</td>
            </tr>
            <tr style="background:rgba(255,255,255,0.03);border-bottom:1px solid rgba(255,255,255,0.06);">
              <td style="padding:12px 16px;">{bm_label}</td>
              <td style="padding:12px 16px;text-align:right;">{colour_pct_val(benchmark_ret)}</td>
            </tr>
            <tr style="border-bottom:1px solid rgba(255,255,255,0.06);">
              <td style="padding:12px 16px;font-size:13px;color:#888;">
                &nbsp;&nbsp;&nbsp;{sym_str}: {prev_str} → {curr_str}
              </td>
              <td></td>
            </tr>
            <tr>
              <td style="padding:12px 16px;font-weight:700;">⚡ Alpha (Portfolio − Benchmark)</td>
              <td style="padding:12px 16px;text-align:right;">{colour_pct_val(alpha)}</td>
            </tr>
          </tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


    fetched_label = bm.get("fetched_at", "—")
    st.markdown(
        f"<p class='benchmark-note'>Benchmark auto-refreshes every {BENCHMARK_REFRESH_MINUTES} minutes. "
        f"Last benchmark fetch: {fetched_label}</p>",
        unsafe_allow_html=True,
    )


with col_b2:
    st.markdown(
        f"""
        <div style="background:rgba(255,255,255,0.04);border-radius:12px;padding:16px;text-align:center;">
          <p style="margin:0;font-size:13px;color:#888;">Portfolio vs BSE 500 (Daily)</p>
          <p style="margin:8px 0 0 0;font-size:28px;font-weight:800;">{colour_pct_val(port_ret)}</p>
          <p style="margin:4px 0 0 0;font-size:13px;color:#888;">vs {colour_pct_val(benchmark_ret)}</p>
          <hr style="border-color:rgba(255,255,255,0.1);margin:12px 0;">
          <p style="margin:0;font-size:13px;color:#888;">Alpha</p>
          <p style="margin:4px 0 0 0;font-size:22px;font-weight:700;">{colour_pct_val(alpha)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


if st.button("🔄 Refresh BSE 500 Benchmark", key="refresh_benchmark"):
    refresh_benchmark_if_due(force=True)
    st.rerun()


st.markdown("</div>", unsafe_allow_html=True)




# ════════════════════════════════════════════════════════════
# SECTION 3 — HOLDINGS TABLE + ASSET PIE
# ════════════════════════════════════════════════════════════
# Section 3 Removed as requested




# ════════════════════════════════════════════════════════════
# SECTION 4 — SECTOR-WISE EQUITY ALLOCATION
# ════════════════════════════════════════════════════════════
st.markdown("## 🏭 Sector-wise Equity Allocation")
st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
if sector_allocation_df is not None and not sector_allocation_df.empty:
    sec_df = sector_allocation_df.copy()
    sec_df.loc[sec_df["Sector"].str.contains("power", case=False, na=False), "Sector"] = "Power"
    sec_df = sec_df.groupby("Sector", as_index=False)["Percent_Allocation"].sum().sort_values("Percent_Allocation", ascending=False)
    fig_sec = px.pie(sec_df, names="Sector", values="Percent_Allocation", hole=0.35)
    fig_sec.update_traces(textposition="inside", textinfo="percent+label")
    fig_sec.update_layout(**pie_layout())
    st.plotly_chart(fig_sec, use_container_width=True)
else:
    st.info("No sector allocation data found in Sectorwise_equity_allocation.xlsx.")
st.markdown("</div>", unsafe_allow_html=True)




# ════════════════════════════════════════════════════════════
# SECTION 5 — ASSET ALLOCATION SUNBURST
# ════════════════════════════════════════════════════════════
st.markdown("## 🧩 Asset Allocation (with Sub-holdings)")
st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
if asset_allocation_df is not None and not asset_allocation_df.empty and asset_breakdown_df is not None and not asset_breakdown_df.empty:
    fig_sun = px.sunburst(asset_breakdown_df, path=["Asset_Type", "Component"], values="Percent_Allocation")
    fig_sun.update_traces(
        texttemplate="%{label}<br>%{value:.2f}%",
        hovertemplate="<b>%{label}</b><br>Allocation: %{value:.2f}%<extra></extra>",
    )
    fig_sun.update_layout(**pie_layout())
    st.plotly_chart(fig_sun, use_container_width=True)
else:
    st.info("No asset allocation data found. Add stocks_with_sectors.xlsx to enable this chart.")
st.markdown("</div>", unsafe_allow_html=True)




# ════════════════════════════════════════════════════════════
# SECTION 6 — DAILY CONTRIBUTION TABLE
# ════════════════════════════════════════════════════════════
st.markdown("## 📌 Daily Contribution by Asset Class")
st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
daily_contribution_df = build_daily_contribution_table(st.session_state.daily_table)
if daily_contribution_df is not None and not daily_contribution_df.empty:
    contrib_disp = daily_contribution_df.copy()
    contrib_disp["Weight"] = contrib_disp["Weight"].map(lambda x: f"{x:.2f}%")
    contrib_disp["Return"] = contrib_disp["Return"].map(lambda x: f"{x:.2f}%").apply(colour_pct)
    contrib_disp["Contribution"] = contrib_disp["Contribution"].map(lambda x: f"{x:.2f}%").apply(colour_pct)
    st.write(contrib_disp.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.info("No daily contribution data. Add allocation files to enable this section.")
st.markdown("</div>", unsafe_allow_html=True)




# ════════════════════════════════════════════════════════════
# SECTION 7 — MARKET CAP ALLOCATION
# ════════════════════════════════════════════════════════════
st.markdown("## 📊 Market Cap Allocation")
st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
if mcap_allocation_df is not None and not mcap_allocation_df.empty:
    fig_mcap = px.pie(mcap_allocation_df, names="Market_Cap", values="Stock_Count", hole=0.35)
    fig_mcap.update_traces(textposition="inside", textinfo="percent+label")
    fig_mcap.update_layout(**pie_layout())
    st.plotly_chart(fig_mcap, use_container_width=True)
else:
    st.info("No market cap data found in mcap_wise_stock_allocation.xlsx.")
st.markdown("</div>", unsafe_allow_html=True)




# ════════════════════════════════════════════════════════════
# SECTION 8 — DAILY TICKER PERFORMANCE
# ════════════════════════════════════════════════════════════
st.markdown("---")
st.markdown("## 📋 Daily Ticker Performance")


with st.expander("🛠 Debug Info", expanded=False):
    st.write("**Raw Excel columns:**", raw_df.columns.tolist())
    st.write("**daily_snapshot columns:**", daily_snapshot.columns.tolist())
    st.dataframe(daily_snapshot.head(6))
    if value_totals:
        st.write(
            f"**File total today:** ₹{value_totals[0]:.4f}  |  "
            f"**File total yesterday:** ₹{value_totals[1]:.4f}  |  "
            f"**File portfolio return:** {file_portfolio_return_pct:.4f}%"
        )


display_df = st.session_state.daily_table.copy()


if display_df.empty:
    st.warning("⚠️ Daily table is empty — open Debug Info expander above.")
else:
    styled = display_df.copy()
    styled["Yesterday Buy/Hold"] = display_df["Yesterday Buy/Hold"].apply(fmt_inr)
    styled["Yesterday Close"] = display_df["Yesterday Close"].apply(fmt_inr)
    styled["Current Price"] = display_df["Current Price"].apply(fmt_inr)
    styled["Current Value"] = display_df["Current Value"].apply(fmt_inr)
    styled["% Change"] = display_df["% Change"].apply(colour_pct)


    st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
    st.write(styled.to_html(escape=False, index=False), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)


import streamlit as st
import pandas as pd


from Dash import get_live_nav_data
from nav_updater import compute_calendar_returns


st.set_page_config(layout="wide")
# =========================
# LOAD DATA FROM DASH
# =========================
data = get_live_nav_data()


nav_df = data["nav_df"]
live_table = data["live_table"]
current_nav = data["current_nav"]
ret = data["return"]
bm_ret = data["bm_return"]


# =========================
# CALENDAR RETURNS
# =========================
st.subheader("📅 Calendar Returns")


calendar_df = compute_calendar_returns(nav_df)


# Integrate current month (Live) into calendar table
current_month_str = pd.Timestamp.today().strftime("%b-%y")
if current_month_str not in calendar_df["Month"].values:
    live_row = pd.DataFrame([{
        "Month": current_month_str,
        "PORT": round(ret, 2),
        "BSE 500": round(bm_ret, 2),
        "Alpha": round(ret - bm_ret, 2)
    }])
    calendar_df = pd.concat([calendar_df, live_row], ignore_index=True)


def color(val):
    if val > 0:
        return "color: #00e676; font-weight: bold;"
    elif val < 0:
        return "color: #ff5252; font-weight: bold;"
    return ""


st.dataframe(
    calendar_df.style.format({
        "PORT": "{:+.2f}%",
        "BSE 500": "{:+.2f}%",
        "Alpha": "{:+.2f}%"
    }).map(color, subset=["PORT", "BSE 500", "Alpha"]),
    use_container_width=True
)


# =========================
# NAV PERFORMANCE CHARTS
# =========================
st.markdown("---")
st.subheader("📈 NAV Performance Charts")


if not nav_df.empty:
    import plotly.graph_objects as go
   
    # Create the figure
    fig = go.Figure()
   
    # Portfolio Line
    fig.add_trace(go.Scatter(
        x=nav_df["DATE"],
        y=nav_df["PORT NAV"],
        mode='lines',
        name='Portfolio',
        line=dict(color='#00e676', width=3),
        hovertemplate='%{x|%d %b %Y}<br>Portfolio: %{y:.2f}'
    ))
   
    # Benchmark Line
    if "BM NAV" in nav_df.columns:
        fig.add_trace(go.Scatter(
            x=nav_df["DATE"],
            y=nav_df["BM NAV"],
            mode='lines',
            name='BSE 500',
            line=dict(color='#ff5252', width=2, dash='dot'),
            hovertemplate='%{x|%d %b %Y}<br>BSE 500: %{y:.2f}'
        ))
   
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(t=20, l=10, r=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis=dict(showgrid=False, title="Date"),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.1)", title="NAV Value (Base 100)"),
        hovermode="x unified"
    )
   
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No NAV data available to plot charts.")
