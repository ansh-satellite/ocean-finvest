import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# Credentials & Paths
# ─────────────────────────────────────────────
TRUEDATA_USERNAME = "tdwsf695"
TRUEDATA_PASSWORD = "ocean@695"
DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

# ─────────────────────────────────────────────
# Page Config & Styling
# ─────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Live Monthly Performance", page_icon="🚀")

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
    .metric-card {
        background: rgba(255,255,255,0.03);
        border-radius: 12px;
        padding: 15px;
        border: 1px solid rgba(255,255,255,0.1);
        text-align: center;
    }
    h1,h2,h3,p,label { color:#e6e6e6 !important; font-family:'Inter',sans-serif; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─────────────────────────────────────────────
# TrueData LTP Fetcher
# ─────────────────────────────────────────────
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
        total = len(ticker_list)
        for i, ticker in enumerate(ticker_list):
            try:
                data = td.get_n_historical_bars(ticker, no_of_bars=1, bar_size="tick")
                if data and len(data) > 0:
                    last = data[-1]
                    ltp = last.get("ltp") or last.get("close") or last.get("Close")
                    if ltp is not None:
                        ltp_map[ticker.upper()] = float(ltp)
            except Exception:
                pass
    except Exception as e:
        st.error(f"❌ TrueData error: {e}")
    finally:
        if td: td.disconnect()
    return ltp_map

# ─────────────────────────────────────────────
# Calculation Helpers
# ─────────────────────────────────────────────
def get_month_performance_data(ticker_df, month_start):
    """
    Finds the start price (Open of first day in month) and end price (Close of last day in month).
    If no data is available in the month, looks back for the nearest previous trading day.
    """
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Search for data WITHIN the month
    month_data = ticker_df[(ticker_df['Date'] >= month_start) & (ticker_df['Date'] <= month_end)]
    
    if not month_data.empty:
        start_price = month_data.iloc[0]['Open']
        end_price = month_data.iloc[-1]['Close']
        return start_price, end_price
    
    # If NO data in this month (e.g. month just started), look back for previous trading day
    # We look back up to 15 days to find the last available close
    for i in range(1, 15):
        target_date = month_start - timedelta(days=i)
        prev_day_data = ticker_df[ticker_df['Date'] == target_date]
        if not prev_day_data.empty:
            # Use the CLOSE of the previous available day as the starting point
            return prev_day_data.iloc[0]['Close'], prev_day_data.iloc[0]['Close']
            
    return None, None

def main():
    st.title("🚀 Live Monthly Ticker Performance")
    
    if not os.path.exists(DATA_PATH):
        st.error(f"❌ File not found: {DATA_PATH}")
        return

    # Load Data
    with st.spinner("Loading data..."):
        df = pd.read_excel(DATA_PATH)
        df['Date'] = pd.to_datetime(df['Date'])
        df.columns = df.columns.str.strip()
    
    today = datetime.today()
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # Rolling 6 months
    months = []
    for i in range(6):
        target = current_month_start
        for _ in range(i):
            target = (target - timedelta(days=1)).replace(day=1)
        months.append(target)
    months = sorted(months, reverse=True) # Newest first
    month_cols = [m.strftime('%b-%Y') for m in months]
    curr_month_label = months[0].strftime('%b-%Y')
    
    # Top Section: Refresh & Summary
    col_header, col_refresh = st.columns([4, 1])
    with col_header:
        st.markdown(f"**Tracking Period:** {months[-1].strftime('%b %Y')} to {months[0].strftime('%b %Y')} (Live)")
    with col_refresh:
        if st.button("🔄 Refresh Live Prices", use_container_width=True):
            with st.spinner("Fetching LTP..."):
                tickers = sorted(df['Ticker'].unique())
                ltp_map = fetch_ltp_truedata(tickers)
                st.session_state.ltp_map = ltp_map
    
    ltp_map = st.session_state.get('ltp_map', {})

    # Calculate Data
    results = []
    tickers = sorted(df['Ticker'].unique())
    for ticker in tickers:
        ticker_df = df[df['Ticker'] == ticker].sort_values('Date')
        row = {'Ticker': ticker}
        for m_start in months:
            m_label = m_start.strftime('%b-%Y')
            
            s_price, e_price = get_month_performance_data(ticker_df, m_start)
            
            # For the current month, override e_price with Live LTP if available
            if m_start == current_month_start:
                live_ltp = ltp_map.get(ticker.upper())
                if live_ltp:
                    e_price = live_ltp
            
            if s_price and e_price and s_price != 0:
                row[m_label] = (e_price - s_price) / s_price * 100
            else:
                row[m_label] = None
        results.append(row)
    
    res_df = pd.DataFrame(results)

    # ─────────────────────────────────────────────
    # Visual Highlights
    # ─────────────────────────────────────────────
    st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
    m1, m2, m3 = st.columns(3)
    
    # Best Performer this month
    if curr_month_label in res_df.columns:
        valid_curr = res_df.dropna(subset=[curr_month_label])
        if not valid_curr.empty:
            top_stock = valid_curr.loc[valid_curr[curr_month_label].idxmax()]
            low_stock = valid_curr.loc[valid_curr[curr_month_label].idxmin()]
            avg_ret = valid_curr[curr_month_label].mean()
            
            with m1:
                st.markdown(f"""
                <div class="metric-card">
                    <p style="margin:0;color:#888;font-size:14px;">Top Gainer ({curr_month_label})</p>
                    <p style="margin:5px 0;color:#00e676;font-size:24px;font-weight:bold;">{top_stock['Ticker']}</p>
                    <p style="margin:0;color:#00e676;font-size:18px;">+{top_stock[curr_month_label]:.2f}%</p>
                </div>
                """, unsafe_allow_html=True)
            with m2:
                st.markdown(f"""
                <div class="metric-card">
                    <p style="margin:0;color:#888;font-size:14px;">Top Loser ({curr_month_label})</p>
                    <p style="margin:5px 0;color:#ff5252;font-size:24px;font-weight:bold;">{low_stock['Ticker']}</p>
                    <p style="margin:0;color:#ff5252;font-size:18px;">{low_stock[curr_month_label]:.2f}%</p>
                </div>
                """, unsafe_allow_html=True)
            with m3:
                color = "#00e676" if avg_ret >= 0 else "#ff5252"
                st.markdown(f"""
                <div class="metric-card">
                    <p style="margin:0;color:#888;font-size:14px;">Average Return ({curr_month_label})</p>
                    <p style="margin:5px 0;color:{color};font-size:24px;font-weight:bold;">{avg_ret:+.2f}%</p>
                    <p style="margin:0;color:#888;font-size:14px;">{len(valid_curr)} Tickers</p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ─────────────────────────────────────────────
    # Main Performance Table
    # ─────────────────────────────────────────────
    st.markdown("### 📊 Performance Heatmap")
    
    # Filter/Search
    search = st.text_input("🔍 Search Ticker", "").upper()
    if search:
        display_df = res_df[res_df['Ticker'].str.contains(search)]
    else:
        display_df = res_df

    def color_returns(val):
        if pd.isna(val): return "color: #444;"
        color = "#00e676" if val >= 0 else "#ff5252"
        return f"color: {color}; font-weight: 700;"

    st.markdown('<div class="glassy-container">', unsafe_allow_html=True)
    st.dataframe(
        display_df.style.format({col: "{:+.2f}%" for col in month_cols}, na_rep="—")
        .map(color_returns, subset=month_cols),
        use_container_width=True,
        height=500
    )
    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
