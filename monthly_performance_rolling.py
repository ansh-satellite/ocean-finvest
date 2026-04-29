import pandas as pd
import streamlit as st
from truedata_ws.websocket.TD import TD
import os

# Credentials
TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"

# Backend Excel File Path
DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\april_stocks.xlsx"

# Streamlit page setup
st.set_page_config(
    page_title="April Performance Dashboard",
    page_icon="📈",
    layout="wide"
)

st.title("📈 April Ticker Performance Dashboard")


# ----------------------------------------
# Fetch Live Data from TrueData
# ----------------------------------------
def fetch_live_data(ticker_list):
    live_map = {}
    td = None

    try:
        td = TD(TRUEDATA_USERNAME, TRUEDATA_PASSWORD, live_port=None)

        progress = st.progress(0)

        for idx, ticker in enumerate(ticker_list):
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

            except Exception as e:
                st.warning(f"Error fetching {ticker}: {e}")

            progress.progress((idx + 1) / len(ticker_list))

    except Exception as e:
        st.error(f"TrueData connection error: {e}")

    finally:
        if td:
            td.disconnect()

    return live_map


# ----------------------------------------
# Build April Performance Table
# ----------------------------------------
def build_april_performance():
    df = pd.read_excel(DATA_PATH)

    df.columns = df.columns.str.strip()

    ticker_col = df.columns[0]
    start_price_col = df.columns[1]

    # Normalize tickers
    df[ticker_col] = (
        df[ticker_col]
        .astype(str)
        .str.upper()
        .str.strip()
        .str.replace(".NS", "", regex=False)
        .str.replace("-EQ", "", regex=False)
    )

    tickers = df[ticker_col].tolist()

    with st.spinner("Fetching live prices from TrueData..."):
        live_prices = fetch_live_data(tickers)

    df["Current Price"] = df[ticker_col].map(live_prices)

    df["Return %"] = (
        (df["Current Price"] - df[start_price_col])
        / df[start_price_col]
    ) * 100

    # Restrict to 2 decimals
    df[start_price_col] = pd.to_numeric(
        df[start_price_col],
        errors="coerce"
    ).round(2)

    df["Current Price"] = pd.to_numeric(
        df["Current Price"],
        errors="coerce"
    ).round(2)

    df["Return %"] = pd.to_numeric(
        df["Return %"],
        errors="coerce"
    ).round(2)

    return df


# ----------------------------------------
# Asset Contribution Table
# ----------------------------------------
def build_asset_contribution_table(df):
    df = df.copy()

    ticker_col = df.columns[0]

    gold_ticker = "GOLDBEES"
    liquid_ticker = "LIQUIDCASE"

    equity_df = df[
        ~df[ticker_col].isin([gold_ticker, liquid_ticker])
    ]

    gold_df = df[
        df[ticker_col] == gold_ticker
    ]

    liquid_df = df[
        df[ticker_col] == liquid_ticker
    ]

    equity_return = (
        equity_df["Return %"].mean()
        if not equity_df.empty else 0
    )

    gold_return = (
        gold_df["Return %"].mean()
        if not gold_df.empty else 0
    )

    liquid_return = (
        liquid_df["Return %"].mean()
        if not liquid_df.empty else 0
    )

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
        "Weight": [asset_df["Weight"].sum()],
        "% Returns": [asset_df["Contribution"].sum()],
        "Contribution": [asset_df["Contribution"].sum()]
    })

    asset_df = pd.concat(
        [asset_df, total_row],
        ignore_index=True
    )

    return asset_df


# ----------------------------------------
# Streamlit UI
# ----------------------------------------
if not os.path.exists(DATA_PATH):
    st.error(f"File not found: {DATA_PATH}")

else:
    if st.button("Fetch April Performance"):

        result_df = build_april_performance()

        st.success("Performance calculated successfully ✅")

        st.subheader("Stock Performance Table")

        st.dataframe(
            result_df.style.format({
                "Start Price": "{:.2f}",
                "Current Price": "{:.2f}",
                "Return %": "{:+.2f}%"
            }),
            use_container_width=True
        )

        asset_contrib_df = build_asset_contribution_table(result_df)

        st.subheader("Asset Contribution Table")

        st.dataframe(
            asset_contrib_df.style.format({
                "Weight": "{:.2f}%",
                "% Returns": "{:.2f}%",
                "Contribution": "{:.2f}%"
            }),
            use_container_width=True
        )

        # Download output
        result_df.to_excel(
            "april_performance.xlsx",
            index=False
        )

        with open("april_performance.xlsx", "rb") as file:
            st.download_button(
                label="📥 Download Performance Report",
                data=file,
                file_name="april_performance.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

MONTHLY_DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\april_stocks.xlsx"