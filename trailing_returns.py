import streamlit as st
import pandas as pd

from Dash import (
    get_live_nav_data,
    calculate_benchmark
)


# =========================================================
# CONFIG
# =========================================================
NAV_FILE_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\NAV.xlsx"

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

st.set_page_config(
    page_title="Trailing Returns Dashboard",
    page_icon="📊",
    layout="wide"
)


# =========================================================
# 1D TRAILING RETURN FROM dummy.py
# =========================================================
# =========================================================
# 1D TRAILING RETURN FROM DASHBOARD SESSION VALUES
# =========================================================
def get_1d_trailing_return():

    if (
        "portfolio_return" not in st.session_state
        or "benchmark_return" not in st.session_state
    ):
        raise ValueError(
            "Dashboard values not found in session"
        )

    port_ret = float(
        st.session_state["portfolio_return"]
    )

    benchmark_ret = float(
        st.session_state["benchmark_return"]
    )

    alpha = (
        port_ret - benchmark_ret
    )

    return {
        "Period": "1D",
        "Portfolio Return": round(
            port_ret, 2
        ),
        "Benchmark Return": round(
            benchmark_ret, 2
        ),
        "Alpha": round(
            alpha, 2
        )
    }

# =========================================================
# FETCH CURRENT NAV VALUES
# =========================================================
def fetch_current_nav_values():

    live_data = get_live_nav_data()

    current_nav = float(
        live_data["current_nav"]
    )

    nav_df = live_data["nav_df"].copy()

    (
        bm_return,
        bm_curr,
        bm_base,
        bm_curr_date,
        bm_base_date
    ) = calculate_benchmark()

    nav_df["DATE"] = pd.to_datetime(
        nav_df["DATE"]
    )

    today = pd.Timestamp.today()
    current_month = today.to_period("M")
    prev_month = current_month - 1

    nav_df["YearMonth"] = (
        nav_df["DATE"].dt.to_period("M")
    )

    prev_month_rows = nav_df[
        nav_df["YearMonth"] == prev_month
    ]

    if prev_month_rows.empty:
        raise ValueError(
            "Previous month benchmark NAV not found"
        )

    base_bm_nav = float(
        prev_month_rows.iloc[-1]["BM NAV"]
    )

    if bm_base == 0:
        raise ValueError(
            "Benchmark base value is zero"
        )

    current_bm_nav = (
        base_bm_nav
        * (bm_curr / bm_base)
    )

    return (
        current_nav,
        current_bm_nav
    )


# =========================================================
# CALCULATE TRAILING RETURNS
# =========================================================
def calculate_trailing_return(days):

    current_nav, current_bm_nav = (
        fetch_current_nav_values()
    )

    nav_df = pd.read_excel(
        NAV_FILE_PATH
    )

    nav_df.columns = (
        nav_df.columns.str.strip()
    )

    nav_df["DATE"] = pd.to_datetime(
        nav_df["DATE"]
    )

    nav_df = nav_df.sort_values(
        "DATE"
    )

    today = pd.Timestamp.today().normalize()

    target_date = (
        today
        - pd.Timedelta(days=days)
    )

    historical_rows = nav_df[
        nav_df["DATE"] <= target_date
    ]

    if historical_rows.empty:
        return None

    selected_row = (
        historical_rows.iloc[-1]
    )

    historical_port_nav = float(
        selected_row["PORT NAV"]
    )

    historical_bm_nav = float(
        selected_row["BM NAV"]
    )

    portfolio_return = (
        (current_nav - historical_port_nav)
        / historical_port_nav
    ) * 100

    benchmark_return = (
        (current_bm_nav - historical_bm_nav)
        / historical_bm_nav
    ) * 100

    alpha = (
        portfolio_return
        - benchmark_return
    )

    return {
        "Period": (
            f"{days}D"
            if days != 90
            else "3M"
        ),
        "Portfolio Return": round(
            portfolio_return, 2
        ),
        "Benchmark Return": round(
            benchmark_return, 2
        ),
        "Alpha": round(
            alpha, 2
        )
    }


# =========================================================
# SINCE INCEPTION
# =========================================================
def calculate_since_inception():

    current_nav, current_bm_nav = (
        fetch_current_nav_values()
    )

    portfolio_return = (
        current_nav - 100
    )

    benchmark_return = (
        current_bm_nav - 100
    )

    alpha = (
        portfolio_return
        - benchmark_return
    )

    return {
        "Period": "Since Inception",
        "Portfolio Return": round(
            portfolio_return, 2
        ),
        "Benchmark Return": round(
            benchmark_return, 2
        ),
        "Alpha": round(
            alpha, 2
        )
    }


# =========================================================
# PAGE FUNCTION
# =========================================================
def show_trailing_returns_page():

    st.title("📊 Trailing Returns Dashboard")

    col1, col2 = st.columns(2)

    with col1:
        if st.button(
            "⬅ Back to Dashboard",
            key="trailing_back_btn"
        ):
            st.session_state.show_trailing_returns = False
            st.rerun()

    with col2:
        if st.button(
            "🔄 Refresh Data",
            key="trailing_refresh_btn"
        ):
            st.rerun()

    try:
        current_nav, current_bm_nav = (
            fetch_current_nav_values()
        )

        st.subheader(
            "Live NAV Snapshot"
        )

        nav_col1, nav_col2 = st.columns(2)

        nav_col1.metric(
            "Current Portfolio NAV",
            f"{current_nav:.2f}"
        )

        nav_col2.metric(
            "Current Benchmark NAV",
            f"{current_bm_nav:.2f}"
        )

        st.subheader(
            "Trailing Returns"
        )

        trailing_results = []

        trailing_results.append(
            get_1d_trailing_return()
        )

        periods = [7, 15, 30, 90]

        for period in periods:

            result = calculate_trailing_return(
                period
            )

            if result:
                trailing_results.append(
                    result
                )

        trailing_results.append(
            calculate_since_inception()
        )

        trailing_df = pd.DataFrame(
            trailing_results
        )

        st.dataframe(
            trailing_df,
            use_container_width=True
        )

    except Exception as e:
        st.error(
            f"Error: {str(e)}"
        )