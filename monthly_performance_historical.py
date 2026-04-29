import os
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# ─────────────────────────────────────────────
# Page Config & Styling
# ─────────────────────────────────────────────
st.set_page_config(layout="wide", page_title="Historical Monthly Performance", page_icon="📋")

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

DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"

def get_start_price(ticker_df, month_start):
    for i in range(0, 10):
        target_date = month_start - timedelta(days=i)
        day_data = ticker_df[ticker_df['Date'] == target_date]
        if not day_data.empty:
            return day_data.iloc[0]['Open'], target_date
    return None, None

def get_end_price(ticker_df, month_start):
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    month_data = ticker_df[(ticker_df['Date'] >= month_start) & (ticker_df['Date'] <= month_end)]
    if not month_data.empty:
        last_row = month_data.iloc[-1]
        return last_row['Close'], last_row['Date']
    return None, None

def main():
    st.title("📋 Historical Monthly Ticker Performance")
    
    if not os.path.exists(DATA_PATH):
        st.error(f"❌ File not found: {DATA_PATH}")
        return

    with st.spinner("Loading Excel data..."):
        df = pd.read_excel(DATA_PATH)
        df['Date'] = pd.to_datetime(df['Date'])
        df.columns = df.columns.str.strip()

    today = datetime.today()
    current_month_start = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    months = []
    for i in range(6):
        target = current_month_start
        for _ in range(i):
            target = (target - timedelta(days=1)).replace(day=1)
        months.append(target)
    
    months = sorted(months, reverse=True)
    month_cols = [m.strftime('%b-%Y') for m in months]
    
    tickers = sorted(df['Ticker'].unique())
    results = []
    
    progress = st.progress(0, text="Calculating performance...")
    for idx, ticker in enumerate(tickers):
        ticker_df = df[df['Ticker'] == ticker].sort_values('Date')
        row = {'Ticker': ticker}
        for m_start in months:
            m_label = m_start.strftime('%b-%Y')
            s_price, _ = get_start_price(ticker_df, m_start)
            e_price, _ = get_end_price(ticker_df, m_start)
            
            if s_price and e_price and s_price != 0:
                row[m_label] = (e_price - s_price) / s_price * 100
            else:
                row[m_label] = None
        results.append(row)
        progress.progress((idx + 1) / len(tickers))
    progress.empty()
    
    res_df = pd.DataFrame(results)

    # Search
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
        height=600
    )
    st.markdown("</div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()
