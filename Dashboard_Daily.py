import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import os

# Set Page Config
st.set_page_config(
    page_title="Daily Tracking Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- Custom CSS for Dark Glassy Theme ---
st.markdown("""
    <style>
    /* Main Background */
    .stApp {
        background-color: #0e1117;
        background-image: linear-gradient(315deg, #0e1117 0%, #161b22 74%);
    }

    /* Glassy Containers */
    .glassy-container {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 16px;
        box-shadow: 0 4px 30px rgba(0, 0, 0, 0.1);
        backdrop-filter: blur(5px);
        -webkit-backdrop-filter: blur(5px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 20px;
        margin-bottom: 20px;
    }

    /* Typography */
    h1, h2, h3, h4, h5, h6, p, label {
        color: #e6e6e6 !important;
        font-family: 'Inter', sans-serif;
    }
    
    /* Metrics */
    [data-testid="stMetricValue"] {
        color: #00e676 !important;
    }

    /* Tables */
    .dataframe {
        background-color: transparent !important;
        color: #e6e6e6 !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: rgba(22, 27, 34, 0.95);
        border-right: 1px solid rgba(255, 255, 255, 0.1);
    }
    </style>
""", unsafe_allow_html=True)


# --- Data Processing Logic for Daily Tracking ---
@st.cache_data
def load_daily_data(file_path):
    if not os.path.exists(file_path):
        return None, None, None
    
    df = pd.read_excel(file_path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values(["Ticker", "Date"])
    
    # Get unique dates sorted
    dates = sorted(df["Date"].dropna().unique())
    if not dates:
        return None, None, None
        
    current_date = dates[-1]
    yesterday_date = dates[-2] if len(dates) >= 2 else current_date
    
    # Filter for today and yesterday
    df_current = df[df["Date"] == current_date].copy()
    df_yesterday = df[df["Date"] == yesterday_date].copy()
    
    # Merge to get side-by-side comparison
    merged = df_current.merge(
        df_yesterday, 
        on="Ticker", 
        suffixes=("_Current", "_Yesterday"), 
        how="left"
    )
    
    # Fill NaN values for yesterday's data in case of new tickers
    merged.fillna({
        "Buy_Hold_Value_Yesterday": 0,
        "Close_Yesterday": 0
    }, inplace=True)

    # Always calculate % change as:
    # (Current Value - Yesterday Close) / Yesterday Close * 100
    merged["Pct_Change"] = np.where(
        merged["Close_Yesterday"] != 0,
        ((merged["Close_Current"] - merged["Close_Yesterday"]) / merged["Close_Yesterday"]) * 100,
        0
    )
    
    return merged, current_date, yesterday_date


def find_column(df, candidate_columns):
    normalized_map = {col.strip().lower(): col for col in df.columns}
    for col in candidate_columns:
        match = normalized_map.get(col.lower())
        if match:
            return match
    return None


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


def get_hedge_mask(ticker_series):
    normalized = normalize_ticker_key(ticker_series).fillna("")
    hedge_symbols = {
        "GOLDBEES",
        "SILVERBEES",
        "LIQUIDCASE",
        "BONDETF",
        "NIFITETF",
    }
    return normalized.isin(hedge_symbols)


def get_benchmark_return_pct(daily_df):
    if daily_df is None or daily_df.empty or "Ticker" not in daily_df.columns:
        return 0.0

    benchmark_keys = {"BSE500", "BSE", "S&PBSE500", "SPBSE500", "BSE-500"}
    ticker_key = normalize_ticker_key(daily_df["Ticker"]).str.replace(" ", "", regex=False)
    benchmark_row = daily_df[ticker_key.isin(benchmark_keys)]

    if benchmark_row.empty:
        return 0.0

    benchmark_close_yday = pd.to_numeric(benchmark_row["Close_Yesterday"], errors="coerce").iloc[0]
    benchmark_close_current = pd.to_numeric(benchmark_row["Close_Current"], errors="coerce").iloc[0]

    if pd.isna(benchmark_close_yday) or benchmark_close_yday == 0 or pd.isna(benchmark_close_current):
        return 0.0

    return ((benchmark_close_current - benchmark_close_yday) / benchmark_close_yday) * 100


def normalize_percent_points(series):
    numeric = pd.to_numeric(series, errors="coerce").fillna(0)
    if numeric.empty:
        return numeric
    # If values are in fraction format (0-1), convert to percentage points.
    if numeric.max() <= 1.0:
        return numeric * 100
    return numeric


@st.cache_data
def load_sector_allocation(file_path):
    if not os.path.exists(file_path):
        return None

    if file_path.lower().endswith(".xlsx"):
        source_df = pd.read_excel(file_path)
    else:
        source_df = pd.read_csv(file_path)

    sector_col = pick_best_live_column(source_df, ["SECTOR", "Sector", "Industry"])
    allocation_col = pick_best_live_column(source_df, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    if not sector_col or not allocation_col:
        return None

    allocation_df = source_df[[sector_col, allocation_col]].copy()
    allocation_df.columns = ["Sector", "Percent_Allocation"]
    allocation_df["Sector"] = allocation_df["Sector"].fillna("Unknown").astype(str).str.strip()
    allocation_df["Percent_Allocation"] = normalize_percent_points(allocation_df["Percent_Allocation"])
    allocation_df = (
        allocation_df.groupby("Sector", as_index=False)["Percent_Allocation"]
        .sum()
        .sort_values("Percent_Allocation", ascending=False)
    )
    allocation_df = allocation_df[allocation_df["Percent_Allocation"] > 0]
    return allocation_df


@st.cache_data
def load_asset_allocation(primary_file_path, fallback_file_path=None):
    def _load_df(path):
        if not path or not os.path.exists(path):
            return None
        if path.lower().endswith(".xlsx"):
            return pd.read_excel(path)
        return pd.read_csv(path)

    source_df = _load_df(primary_file_path)
    if source_df is None and fallback_file_path:
        source_df = _load_df(fallback_file_path)
    if source_df is None:
        return None

    asset_col = pick_best_live_column(source_df, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
    allocation_col = pick_best_live_column(source_df, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    if not asset_col or not allocation_col:
        if fallback_file_path and fallback_file_path != primary_file_path:
            source_df = _load_df(fallback_file_path)
            if source_df is None:
                return None
            asset_col = pick_best_live_column(source_df, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
            allocation_col = pick_best_live_column(source_df, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
        if not asset_col or not allocation_col:
            return None

    asset_df = source_df[[asset_col, allocation_col]].copy()
    asset_df.columns = ["Asset_Type", "Percent_Allocation"]
    asset_df["Asset_Type"] = asset_df["Asset_Type"].fillna("Unknown").astype(str).str.strip()
    asset_df["Percent_Allocation"] = normalize_percent_points(asset_df["Percent_Allocation"])
    asset_df = (
        asset_df.groupby("Asset_Type", as_index=False)["Percent_Allocation"]
        .sum()
        .sort_values("Percent_Allocation", ascending=False)
    )
    asset_df = asset_df[asset_df["Percent_Allocation"] > 0]
    return asset_df


@st.cache_data
def load_asset_breakdown(file_path):
    if not os.path.exists(file_path):
        return None

    if file_path.lower().endswith(".xlsx"):
        source_df = pd.read_excel(file_path)
    else:
        source_df = pd.read_csv(file_path)

    asset_col = pick_best_live_column(source_df, ["ASSET_TYPE", "Asset_Type", "Asset", "Asset Class", "Category"])
    allocation_col = pick_best_live_column(source_df, ["Percent_Allocation", "Allocation", "Weightage", "WEIGHTAGE"])
    component_col = pick_best_live_column(source_df, ["STOCKS", "Ticker", "Symbol", "SECTOR", "Sector", "Name"])

    if not asset_col or not allocation_col or not component_col:
        return None

    breakdown_df = source_df[[asset_col, component_col, allocation_col]].copy()
    breakdown_df.columns = ["Asset_Type", "Component", "Percent_Allocation"]
    breakdown_df["Asset_Type"] = breakdown_df["Asset_Type"].fillna("Unknown").astype(str).str.strip()
    breakdown_df["Component"] = breakdown_df["Component"].fillna("Unknown").astype(str).str.strip()
    breakdown_df["Percent_Allocation"] = normalize_percent_points(breakdown_df["Percent_Allocation"])
    breakdown_df = (
        breakdown_df.groupby(["Asset_Type", "Component"], as_index=False)["Percent_Allocation"]
        .sum()
        .sort_values(["Asset_Type", "Percent_Allocation"], ascending=[True, False])
    )
    breakdown_df = breakdown_df[breakdown_df["Percent_Allocation"] > 0]
    return breakdown_df


def apply_target_asset_weights(asset_breakdown_df, asset_allocation_df):
    if asset_breakdown_df is None or asset_breakdown_df.empty:
        return asset_breakdown_df

    weighted_df = asset_breakdown_df.copy()
    weighted_df["Asset_Key"] = weighted_df["Asset_Type"].astype(str).str.upper().str.strip()

    target_map = {}
    if asset_allocation_df is not None and not asset_allocation_df.empty:
        target_df = asset_allocation_df.copy()
        target_df["Asset_Key"] = target_df["Asset_Type"].astype(str).str.upper().str.strip()
        target_map = (
            target_df.groupby("Asset_Key", as_index=False)["Percent_Allocation"]
            .sum()
            .set_index("Asset_Key")["Percent_Allocation"]
            .to_dict()
        )

    grouped_parts = []
    for asset_key, group in weighted_df.groupby("Asset_Key"):
        group = group.copy()
        target_pct = target_map.get(asset_key, group["Percent_Allocation"].sum())
        if len(group) > 0:
            group["Percent_Allocation"] = target_pct / len(group)
        grouped_parts.append(group)

    result_df = pd.concat(grouped_parts, ignore_index=True)
    return result_df.drop(columns=["Asset_Key"])


def get_weighted_portfolio_return_pct(daily_df, asset_breakdown_df):
    if (
        daily_df is None or daily_df.empty
        or asset_breakdown_df is None or asset_breakdown_df.empty
    ):
        return None

    returns_df = daily_df[["Ticker", "Pct_Change"]].copy()
    returns_df["Ticker_Key"] = normalize_ticker_key(returns_df["Ticker"])
    returns_df["Pct_Change"] = pd.to_numeric(returns_df["Pct_Change"], errors="coerce").fillna(0.0)
    returns_df = returns_df.groupby("Ticker_Key", as_index=False)["Pct_Change"].first()

    weights_df = asset_breakdown_df[["Component", "Percent_Allocation"]].copy()
    weights_df["Ticker_Key"] = normalize_ticker_key(weights_df["Component"])
    weights_df["Weight_Pct"] = pd.to_numeric(weights_df["Percent_Allocation"], errors="coerce").fillna(0.0)

    merged_df = weights_df.merge(returns_df, on="Ticker_Key", how="left")
    merged_df["Pct_Change"] = merged_df["Pct_Change"].fillna(0.0)
    total_weight = merged_df["Weight_Pct"].sum()
    if total_weight == 0:
        return None

    weighted_return_pct = (merged_df["Weight_Pct"] * merged_df["Pct_Change"]).sum() / total_weight
    return float(weighted_return_pct)


def get_live_portfolio_return_pct(daily_df):
    if daily_df is None or daily_df.empty:
        return None

    yday_buyhold = pd.to_numeric(daily_df["Buy_Hold_Value_Yesterday"], errors="coerce").fillna(0.0)
    pct_change = pd.to_numeric(daily_df["Pct_Change"], errors="coerce").fillna(0.0)
    live_current_buyhold = yday_buyhold * (1 + (pct_change / 100.0))

    total_yday = yday_buyhold.sum()
    if total_yday == 0:
        return None

    return float(((live_current_buyhold.sum() - total_yday) / total_yday) * 100.0)


def build_daily_contribution_table(daily_df, asset_allocation_df, asset_breakdown_df):
    if (
        daily_df is None or daily_df.empty
        or asset_allocation_df is None or asset_allocation_df.empty
    ):
        return None

    returns_df = daily_df[["Ticker", "Pct_Change"]].copy()
    returns_df["Ticker_Key"] = normalize_ticker_key(returns_df["Ticker"])
    returns_df["Pct_Change"] = pd.to_numeric(returns_df["Pct_Change"], errors="coerce").fillna(0.0)
    returns_df = returns_df.groupby("Ticker_Key", as_index=False)["Pct_Change"].first()
    returns_map = dict(zip(returns_df["Ticker_Key"], returns_df["Pct_Change"]))

    if asset_breakdown_df is None or asset_breakdown_df.empty:
        contribution_df = asset_allocation_df.copy()
        contribution_df["Weight"] = pd.to_numeric(contribution_df["Percent_Allocation"], errors="coerce").fillna(0.0)
        contribution_df["Return"] = 0.0
        contribution_df["Contribution"] = (contribution_df["Weight"] * contribution_df["Return"]) / 100.0
        return contribution_df.rename(columns={"Asset_Type": "Particular"})[["Particular", "Weight", "Return", "Contribution"]]

    breakdown_df = asset_breakdown_df.copy()
    breakdown_df["Asset_Key"] = breakdown_df["Asset_Type"].astype(str).str.upper().str.strip()
    breakdown_df["Ticker_Key"] = normalize_ticker_key(breakdown_df["Component"])
    breakdown_df["Component_Weight"] = pd.to_numeric(breakdown_df["Percent_Allocation"], errors="coerce").fillna(0.0)

    rows = []
    for _, asset_row in asset_allocation_df.iterrows():
        asset_name = str(asset_row["Asset_Type"]).strip()
        asset_key = asset_name.upper()
        asset_weight = float(pd.to_numeric(asset_row["Percent_Allocation"], errors="coerce"))

        asset_components = breakdown_df[breakdown_df["Asset_Key"] == asset_key].copy()
        if asset_components.empty:
            asset_return = 0.0
        else:
            asset_components["Component_Return"] = asset_components["Ticker_Key"].map(returns_map).fillna(0.0)
            component_weight_total = asset_components["Component_Weight"].sum()
            if component_weight_total > 0:
                asset_return = (
                    (asset_components["Component_Weight"] * asset_components["Component_Return"]).sum()
                    / component_weight_total
                )
            else:
                asset_return = asset_components["Component_Return"].mean()

        contribution = (asset_weight * asset_return) / 100.0
        rows.append({
            "Particular": asset_name,
            "Weight": asset_weight,
            "Return": asset_return,
            "Contribution": contribution,
        })

    return pd.DataFrame(rows).sort_values("Weight", ascending=False)


@st.cache_data
def load_mcap_allocation(file_path):
    if not os.path.exists(file_path):
        return None

    if file_path.lower().endswith(".xlsx"):
        source_df = pd.read_excel(file_path)
    else:
        source_df = pd.read_csv(file_path)

    mcap_col = pick_best_live_column(source_df, ["MCAP", "Mcap", "Market Cap", "Market_Cap"])
    if not mcap_col:
        return None

    mcap_df = source_df[[mcap_col]].copy()
    mcap_df.columns = ["Market_Cap"]
    mcap_df["Market_Cap"] = mcap_df["Market_Cap"].fillna("Unknown").astype(str).str.strip()
    mcap_df = (
        mcap_df.groupby("Market_Cap", as_index=False)
        .size()
        .rename(columns={"size": "Stock_Count"})
        .sort_values("Stock_Count", ascending=False)
    )
    total_count = mcap_df["Stock_Count"].sum()
    mcap_df["Allocation_Pct"] = np.where(
        total_count > 0,
        (mcap_df["Stock_Count"] / total_count) * 100,
        0
    )
    return mcap_df


# --- Main App ---
st.title("🚀 Daily Momentum Tracking Dashboard")

DATA_PATH = os.path.join("MOMENTUM_DB_2 copy", "Trials", "Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx")
SECTOR_ALLOCATION_PATH = os.path.join("Sectorwise_equity_allocation.xlsx")
ASSET_ALLOCATION_PATH = os.path.join("stocks_with_sectors.xlsx")
MCAP_ALLOCATION_PATH = os.path.join("mcap_wise_stock_allocation.xlsx")

if not os.path.exists(DATA_PATH):
    st.error(f"Data file not found at: {DATA_PATH}. Please check the path.")
else:
    refresh_col, info_col = st.columns([1, 3])
    with refresh_col:
        if st.button("🔄 Restart / Refresh Now", use_container_width=True, type="primary"):
            st.cache_data.clear()
            st.rerun()
    with info_col:
        st.caption("Data updates every 15 minutes. Click refresh to pull latest values instantly.")

    with st.spinner("Processing Daily Data..."):
        daily_df, current_date, yesterday_date = load_daily_data(DATA_PATH)

    if daily_df is not None:
        st.caption(f"📅 Current Date: **{pd.to_datetime(current_date).strftime('%d %B %Y')}** | Previous Date: **{pd.to_datetime(yesterday_date).strftime('%d %B %Y')}**")

        # Load allocation/mapping data once for charts and weighted return logic.
        sector_allocation_df = load_sector_allocation(SECTOR_ALLOCATION_PATH)
        asset_allocation_df = load_asset_allocation(SECTOR_ALLOCATION_PATH, ASSET_ALLOCATION_PATH)
        asset_breakdown_df = load_asset_breakdown(ASSET_ALLOCATION_PATH)
        asset_breakdown_df = apply_target_asset_weights(asset_breakdown_df, asset_allocation_df)
        mcap_allocation_df = load_mcap_allocation(MCAP_ALLOCATION_PATH)

        # Metrics
        total_value_current = daily_df["Buy_Hold_Value_Current"].sum()
        total_value_yesterday = daily_df["Buy_Hold_Value_Yesterday"].sum()
        portfolio_change = total_value_current - total_value_yesterday
        portfolio_daily_return_pct = (portfolio_change / total_value_yesterday * 100) if total_value_yesterday else 0
        live_portfolio_return_pct = get_live_portfolio_return_pct(daily_df)
        weighted_portfolio_return_pct = get_weighted_portfolio_return_pct(daily_df, asset_breakdown_df)
        daily_contribution_df = build_daily_contribution_table(daily_df, asset_allocation_df, asset_breakdown_df)
        portfolio_return_pct = (
            live_portfolio_return_pct
            if live_portfolio_return_pct is not None
            else (
                weighted_portfolio_return_pct
                if weighted_portfolio_return_pct is not None
                else portfolio_daily_return_pct
            )
        )

        # Display Metrics in Glassy Container
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Portfolio Value", f"₹ {total_value_current:,.2f}")
        col2.metric("Portfolio Daily Change", f"{portfolio_daily_return_pct:.2f}%")
        col3.metric("Tracked Tickers", len(daily_df))
        
        # Count positive vs negative movers
        gainers = len(daily_df[daily_df["Pct_Change"] > 0])
        losers = len(daily_df[daily_df["Pct_Change"] < 0])
        col4.metric("Advance / Decline", f"{gainers} / {losers}")
        st.markdown('</div>', unsafe_allow_html=True)

        # Daily Return Data
        benchmark_return_pct = get_benchmark_return_pct(daily_df)
        alpha_pct = portfolio_return_pct - (benchmark_return_pct / 100)
        st.markdown("### 📈 Daily Return Data")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        daily_return_df = pd.DataFrame([{
            "Portfolio Return": f"{portfolio_return_pct:.2f}%",
           "Benchmark Return (BSE500)": f"{(benchmark_return_pct/100):.2f}%",
           "Alpha": f"{alpha_pct:.2f}%"
}])
        st.dataframe(daily_return_df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 🏭 Sector-wise Equity Allocation")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        if sector_allocation_df is not None and not sector_allocation_df.empty:
            # Keep "Power" bucket consistent if file has naming variants.
            power_like_mask = sector_allocation_df["Sector"].str.contains("power", case=False, na=False)
            sector_allocation_df.loc[power_like_mask, "Sector"] = "Power"
            sector_allocation_df = (
                sector_allocation_df.groupby("Sector", as_index=False)["Percent_Allocation"]
                .sum()
                .sort_values("Percent_Allocation", ascending=False)
            )

            sector_pie = px.pie(
                sector_allocation_df,
                names="Sector",
                values="Percent_Allocation",
                hole=0.35
            )
            sector_pie.update_traces(textposition="inside", textinfo="percent+label")
            sector_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e6e6e6"),
                margin=dict(t=10, l=10, r=10, b=10)
            )
            st.plotly_chart(sector_pie, use_container_width=True)
        else:
            st.info("No sector-wise allocation data available in Sectorwise_equity_allocation.xlsx.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 🧩 Asset Allocation (with Sub-holdings)")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        if (
            asset_allocation_df is not None and not asset_allocation_df.empty
            and asset_breakdown_df is not None and not asset_breakdown_df.empty
        ):
            asset_sunburst = px.sunburst(
                asset_breakdown_df,
                path=["Asset_Type", "Component"],
                values="Percent_Allocation"
            )
            asset_sunburst.update_traces(
                texttemplate="%{label}<br>%{value:.2f}%",
                hovertemplate="<b>%{label}</b><br>Allocation: %{value:.2f}%<extra></extra>"
            )
            asset_sunburst.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e6e6e6"),
                margin=dict(t=10, l=10, r=10, b=10)
            )
            st.plotly_chart(asset_sunburst, use_container_width=True)
        else:
            st.info("No asset allocation data available in mapping files.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 📌 Daily Contribution")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        if daily_contribution_df is not None and not daily_contribution_df.empty:
            contribution_display_df = daily_contribution_df.copy()
            contribution_display_df["Weight"] = contribution_display_df["Weight"].map(lambda x: f"{x:.2f}%")
            contribution_display_df["Return"] = contribution_display_df["Return"].map(lambda x: f"{x:.2f}%")
            contribution_display_df["Contribution"] = contribution_display_df["Contribution"].map(lambda x: f"{x:.2f}%")
            st.dataframe(contribution_display_df, use_container_width=True, hide_index=True)
        else:
            st.info("No daily contribution data available.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 📊 Market Cap Allocation")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        if mcap_allocation_df is not None and not mcap_allocation_df.empty:
            mcap_pie = px.pie(
                mcap_allocation_df.sort_values("Stock_Count", ascending=False),
                names="Market_Cap",
                values="Stock_Count",
                hole=0.35
            )
            mcap_pie.update_traces(textposition="inside", textinfo="percent+label")
            mcap_pie.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#e6e6e6"),
                margin=dict(t=10, l=10, r=10, b=10)
            )
            st.plotly_chart(mcap_pie, use_container_width=True)
        else:
            st.info("No market cap allocation data available in mcap_wise_stock_allocation.xlsx.")
        st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("### 📋 Daily Ticker Performance")
        st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
        
        # Prepare Table Data
        # Requested Columns: 
        # 1. Ticker List
        # 2. Current Date
        # 3. Buy Hold Value of Yesterday and Current
        # 4. OV (Opening value of yesterday closing and current value)
        # 5. % Change
        
        table_df = daily_df[[
            "Ticker", 
            "Date_Current",
            "Buy_Hold_Value_Yesterday",
            "Close_Yesterday",  # Yesterday Closing
            "Open_Current",     # Today Opening
            "Close_Current",    # Current Value
            "Pct_Change"
        ]].copy()

        table_df["Buy_Hold_Value_Current"] = (
            pd.to_numeric(table_df["Buy_Hold_Value_Yesterday"], errors="coerce").fillna(0.0)
            * (
                1
                + (
                    pd.to_numeric(table_df["Pct_Change"], errors="coerce").fillna(0.0) / 100.0
                )
            )
        )
        
        table_df["Date_Current"] = pd.to_datetime(table_df["Date_Current"]).dt.strftime('%Y-%m-%d')
        
        # Formatting
        table_df["Buy_Hold_Value_Yesterday"] = table_df["Buy_Hold_Value_Yesterday"].map('₹ {:,.2f}'.format)
        table_df["Buy_Hold_Value_Current"] = table_df["Buy_Hold_Value_Current"].map('₹ {:,.2f}'.format)
        table_df["Close_Yesterday"] = table_df["Close_Yesterday"].map('₹ {:,.2f}'.format)
        table_df["Open_Current"] = table_df["Open_Current"].map('₹ {:,.2f}'.format)
        table_df["Close_Current"] = table_df["Close_Current"].map('₹ {:,.2f}'.format)
        
        # Format % Change (handle potential string vs float issues if %change_Current was a string)
        table_df["Pct_Change"] = pd.to_numeric(table_df["Pct_Change"], errors='coerce').map('{:,.2f}%'.format)
        
        st.dataframe(
            table_df.rename(columns={
                "Ticker": "Ticker List",
                "Date_Current": "Current Date",
                "Buy_Hold_Value_Yesterday": "Yesterday Buy/Hold",
                "Buy_Hold_Value_Current": "Current Buy/Hold",
                "Close_Yesterday": "Yesterday Close",
                "Open_Current": "Today Open",
                "Close_Current": "Current Value",
                "Pct_Change": "% Change"
            }),
            use_container_width=True,
            hide_index=True,
            height=600
        )
        st.markdown('</div>', unsafe_allow_html=True)
```