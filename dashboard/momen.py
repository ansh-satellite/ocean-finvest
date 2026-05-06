import os
import time
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from pathlib import Path
from truedata import TD_hist

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
warnings.filterwarnings('ignore')
 
# --- Configuration ---
SCRIPT_DIR = Path(__file__).parent
DATA_DIR   = SCRIPT_DIR / "data"
# Universe file is located in the data folder
UNIVERSE   = DATA_DIR / "Nifty_500_2025_Apr.csv"

# --- Helper Utilities ---
def safe_save_excel(df, path):
    """
    Saves a dataframe to Excel, handling PermissionError if the file is open.
    """
    try:
        df.to_excel(path, index=False)
        logger.info(f"Successfully saved: {path}")
    except PermissionError:
        logger.error(f"❌ PERMISSION DENIED: Could not save to {path}.")
        logger.error("   Please CLOSE THE FILE in Excel and run the script again.")
    except Exception as e:
        logger.error(f"❌ FAILED TO SAVE {path}: {e}")

# --- Credential Management ---
def get_credentials():
    """
    Retrieves TrueData credentials from Streamlit secrets (if available)
    or a local secrets.toml file.
    """
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "TRUEDATA_USERNAME" in st.secrets:
            return st.secrets["TRUEDATA_USERNAME"], st.secrets["TRUEDATA_PASSWORD"]
        if hasattr(st, "secrets") and "truedata" in st.secrets:
            return st.secrets["truedata"].get("username"), st.secrets["truedata"].get("password")
    except ImportError:
        pass

    try:
        import tomllib
    except ImportError:
        try:
            import pip._vendor.tomli as tomllib
        except ImportError:
            tomllib = None

    if tomllib:
        script_dir = Path(__file__).parent
        secrets_paths = [
            script_dir / ".streamlit" / "secrets.toml",
            Path(".streamlit/secrets.toml")
        ]
        for secrets_path in secrets_paths:
            if secrets_path.exists():
                with open(secrets_path, "rb") as f:
                    secrets = tomllib.load(f)
                    # Check both flat and nested structures
                    user = secrets.get("TRUEDATA_USERNAME") or secrets.get("truedata", {}).get("username")
                    pwd = secrets.get("TRUEDATA_PASSWORD") or secrets.get("truedata", {}).get("password")
                    if user and pwd:
                        return user, pwd
    
    return None, None

# --- Data Fetching ---
def fetch_truedata_history(ticker_list, duration='1 Y', bar_size='EOD', sleep_time=0.1):
    """
    Fetches historical EOD data from TrueData for a list of tickers.
    """
    username, password = get_credentials()
    if not username or not password:
        logger.error("TrueData credentials not found!")
        return pd.DataFrame(), ticker_list

    td_hist = TD_hist(username, password)
    df_list = []
    error_list = []

    for ticker in ticker_list:
        try:
            # Defensive check: Ensure ticker is valid string
            if not isinstance(ticker, str) or not ticker.strip():
                logger.warning(f"Skipping invalid ticker: {ticker}")
                continue

            df = td_hist.get_historic_data([ticker], duration=duration, bar_size=bar_size)
            
            # Explicitly check for None or empty dataframe before processing
            if df is None or (isinstance(df, pd.DataFrame) and df.empty):
                logger.warning(f"No data returned for {ticker}")
                error_list.append(ticker)
                continue

            df['Ticker'] = ticker
            rename_dict = {}
            for col in ['timestamp', 'datetime', 'date']:
                if col in df.columns:
                    rename_dict[col] = 'Date'
            
            rename_dict.update({
                'high': 'High', 'low': 'Low', 'close': 'Close', 'open': 'Open'
            })
            df = df.rename(columns=rename_dict)
            df_list.append(df)
            logger.info(f"Fetched data for {ticker} ({len(df)} rows).")
            time.sleep(sleep_time)

        except Exception as e:
            logger.error(f"Failed to fetch data for {ticker}: {e}")
            error_list.append(ticker)

    final_df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    if not final_df.empty:
        final_df['Date'] = pd.to_datetime(final_df['Date'])
    return final_df, error_list

# --- Momentum Strategy Logic ---
def run_momentum_strategy(universe_file, start_date, end_date, top_n, output_root="Momentum_Results"):
    """
    Generates momentum rankings for a stock universe over rolling 6-month windows.
    """
    if universe_file.endswith(".csv"):
        stock_list = pd.read_csv(universe_file)[["Symbol", "ISIN Code"]]
    else:
        stock_list = pd.read_excel(universe_file)[["Symbol", "ISIN Code"]]
    
    stock_list["Ticker"] = stock_list["Symbol"]
    
    # Ensure forced tickers are in the symbol list for fetching
    forced_universe_additions = [
        "ABB", "ACUTAAS","ATHERENERG", "BHARATFORG", "BHEL", "BSE", "COALINDIA", 
        "GESHIP", "GLENMARK", "GVT&D", "HINDALCO", "IPCALAB", "KIRLOSENG", 
        "MAHABANK", "MCX", "NATIONALUM", "SAIL", "TORNTPOWER", 
        "VEDL", "VTL", "CPSEETF", "LIQUIDCASE", "GOLDBEES", "NEXT50IETF"
    ]
    for ticker in forced_universe_additions:
        if ticker not in stock_list["Ticker"].values:
            new_row = pd.DataFrame({"Symbol": [ticker], "Ticker": [ticker], "ISIN Code": [np.nan]})
            stock_list = pd.concat([stock_list, new_row], ignore_index=True)
            
    symbol_list = stock_list["Ticker"].tolist()
    universe_name = Path(universe_file).stem
    output_dir = os.path.join(output_root, f"{universe_name}_{top_n}_stocks_results")
    os.makedirs(output_dir, exist_ok=True)

    total_start = pd.to_datetime(start_date)
    total_end = pd.to_datetime(end_date)

    logger.info(f"Downloading price data for {len(symbol_list)} symbols...")
    data, errors = fetch_truedata_history(symbol_list, duration='10 Y', bar_size='EOD')
    if data.empty:
        return None

    data = data[['Date', 'Close', 'Ticker']].drop_duplicates(subset=['Date', 'Ticker'])
    prices_all = data.pivot(index="Date", columns="Ticker", values="Close").sort_index()

    # Create Rolling Windows
    windows = []
    current_start = total_start
    while True:
        current_end = current_start + relativedelta(months=6)
        if current_end > total_end:
            break
        window_prices = prices_all.loc[(prices_all.index >= current_start) & (prices_all.index < current_end)].copy()
        if not window_prices.empty:
            windows.append((current_start, current_end, window_prices))
        current_start += relativedelta(months=1)

    # Process Each Window
    for start, end, prices in windows:
        file_suffix = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        output_file = os.path.join(output_dir, f"momentum_{file_suffix}.xlsx")
        
        # Check if window file exists to respect "don't change previous data"
        # Exception: Always re-generate May 2026 to pick up latest manual overrides
        if os.path.exists(output_file) and end.strftime('%Y-%m-%d') != '2026-05-01':
            logger.info(f"Window result already exists: {output_file}. Skipping calculation.")
            continue
            
        prices.dropna(axis=1, how='all', inplace=True)
        if prices.empty: continue

        # Calculate Momentum
        monthclose = prices.groupby(prices.index.strftime('%Y-%m')).tail(1)
        monthstart = prices.groupby(prices.index.strftime('%Y-%m')).head(1)
        monthstart.index = monthclose.index
        monchange = (monthclose - monthstart) / monthstart
        MOM = (monchange + 1).product() - 1
        mom = MOM * 100

        # Daily returns for FIP
        daily_ret = prices.pct_change(fill_method=None)
        positivechange = (daily_ret[daily_ret > 0].count() / daily_ret.count()) * 100
        negativechange = (daily_ret[daily_ret < 0].count() / daily_ret.count()) * 100

        result = pd.concat([positivechange, negativechange, mom], axis=1, join='inner')
        result.columns = ["Positive", "Negative", "Momentum"]
        result = result.reset_index().rename(columns={'index': 'Ticker'})
        result = pd.merge(result, stock_list[["Ticker", "ISIN Code"]], on="Ticker", how="left")

        # Ranking
        df = result.copy()
        df["Rank_Mom"] = df["Momentum"].rank(method='min', ascending=False)
        df['FIP'] = df.apply(lambda row: row['Negative'] - row['Positive'] if row['Momentum'] > 0 else np.nan, axis=1)
        df.dropna(inplace=True)
        df["FIP_rank"] = df["FIP"].rank(method="first", ascending=True)
        df["Combined_Rank"] = df["Rank_Mom"] + df["FIP_rank"]
        
        # Hardcoded overrides
        if end.strftime('%Y-%m-%d') == '2026-01-01':
            df = df[~(df['Ticker'].isin(['MARUTI', 'PTCIL']))]
            
        if end.strftime('%Y-%m-%d') == '2026-05-01':
            logger.info("Applying May 2026 specific selection override...")
            # User's explicit equity list (Removed Siemens and AdaniEnsol, added Acutaas and AtherEnerg)
            may_equity_selection = [
                "ABB", "ACUTAAS", "ATHERENERG", "BHARATFORG", "BHEL", "BSE", "COALINDIA", 
                "GESHIP", "GLENMARK", "GVT&D", "HINDALCO", "IPCALAB", "KIRLOSENG", 
                "MAHABANK", "MCX", "NATIONALUM", "SAIL", "TORNTPOWER", 
                "VEDL", "VTL"
            ]
            
            # Clear existing selection and force these 20
            forced_df_list = []
            for t in may_equity_selection:
                if t in result['Ticker'].values:
                    ft_row = result[result['Ticker'] == t].copy()
                else:
                    # Fallback if ticker not in result (should not happen if fetched)
                    ft_row = pd.DataFrame({
                        "Ticker": [t], "Positive": [0], "Negative": [0], "Momentum": [0], 
                        "ISIN Code": [np.nan], "Rank_Mom": [0], "FIP": [0], "FIP_rank": [0], 
                        "Combined_Rank": [-999.0]
                    })
                ft_row['Combined_Rank'] = -999.0
                forced_df_list.append(ft_row)
            
            df = pd.concat(forced_df_list, ignore_index=True).sort_values(by="Combined_Rank")

        df = df.sort_values(by="Combined_Rank", ascending=True)

        # CMP Filter (Price < 7500)
        last_close = prices.iloc[-1]
        df["CMP"] = df["Ticker"].map(last_close)
        df = df[df["CMP"] <= 7500].copy()
        
        df = df.head(top_n)
        df["Real_Rank"] = range(1, len(df) + 1)
        df["End_Date"] = end.strftime('%Y-%m-%d')

        output_file = os.path.join(output_dir, f"momentum_{file_suffix}.xlsx")
        safe_save_excel(df, output_file)

    # Create Master Summary
    master_data = []
    for file in os.listdir(output_dir):
        if file.startswith("momentum_") and file.endswith(".xlsx"):
            window_df = pd.read_excel(os.path.join(output_dir, file))
            master_data.append(window_df[["End_Date", "ISIN Code", "Ticker", 'Real_Rank']])

    if master_data:
        master_df = pd.concat(master_data, ignore_index=True)
        master_file_path = os.path.join(output_dir, "master_momentum_summary.xlsx")
        safe_save_excel(master_df, master_file_path)
        return master_file_path
    return None

# --- Portfolio Processing Logic ---
def process_portfolio(nav_df, ticker_data, initial_value=75, inception_date=None):
    """
    Values a portfolio month-by-month based on rebalance dates.
    """
    df_lis = []
    last_month_value = {}
    last_month_quantity = {}

    nav_df = nav_df.sort_values(['Date', 'Ticker']).copy()
    nav_df['Date'] = pd.to_datetime(nav_df['Date'])
    ticker_data = ticker_data.sort_values(['Ticker', 'Date']).copy()
    ticker_data['Date'] = pd.to_datetime(ticker_data['Date'])

    if inception_date is None:
        inception_date = nav_df['Date'].min()
    else:
        inception_date = pd.to_datetime(inception_date)

    for year_month in nav_df['Year-Month'].drop_duplicates():
        month_nav = nav_df[nav_df['Year-Month'] == year_month].copy()
        tickers = month_nav['Ticker'].dropna().unique().tolist()
        selection_date = pd.to_datetime(month_nav['Date'].min())
        year_month_date = pd.to_datetime(f"{year_month}-01")

        prev_month_start = year_month_date - relativedelta(months=2)
        curr_month_start = year_month_date
        curr_month_end = year_month_date + pd.offsets.MonthEnd(0)

        stock_data = ticker_data[
            (ticker_data['Date'] >= prev_month_start) & (ticker_data['Date'] <= curr_month_end) & (ticker_data['Ticker'].isin(tickers))
        ].copy()
        stock_data = stock_data[stock_data['Date'] >= inception_date].copy()
        stock_data['%change'] = stock_data.groupby('Ticker')['Close'].pct_change()

        stock_data_flt = stock_data[(stock_data['Date'] >= curr_month_start) & (stock_data['Date'] <= curr_month_end)].copy()
        if stock_data_flt.empty: continue

        if not last_month_value:
            allocation_per_stock = initial_value / len(tickers)
            stock_allocations = {t: allocation_per_stock for t in tickers}
        else:
            stock_allocations = {t: last_month_value[t] for t in tickers if t in last_month_value}
            dropped_stocks = [t for t in last_month_value if t not in tickers]
            dropped_value = sum(last_month_value[t] for t in dropped_stocks)
            new_stocks = [t for t in tickers if t not in last_month_value]
            if new_stocks:
                alloc = dropped_value / len(new_stocks) if dropped_value else 0.0
                for t in new_stocks: stock_allocations[t] = alloc

        for ticker, init_val in stock_allocations.items():
            ticker_index = stock_data_flt[stock_data_flt['Ticker'] == ticker].index
            if ticker_index.empty: continue
            
            stock_data_flt.loc[ticker_index, 'Initial_Allocation'] = init_val
            stock_data_flt.loc[ticker_index, 'Selection_Date'] = selection_date
            stock_data_flt.loc[ticker_index, 'Buy_Hold_Value'] = init_val * ((1 + stock_data_flt.loc[ticker_index, '%change'].fillna(0)).cumprod())
            
            buy_price = float(stock_data_flt.loc[ticker_index].iloc[0]['Close'])
            quantity = last_month_quantity.get(ticker, init_val / buy_price if buy_price else 0.0)
            stock_data_flt.loc[ticker_index, 'Buy_Price'] = buy_price
            stock_data_flt.loc[ticker_index, 'Quantity'] = quantity
            if 'Real_Rank' in month_nav.columns:
                stock_data_flt.loc[ticker_index, 'Real_Rank'] = month_nav.loc[month_nav['Ticker'] == ticker, 'Real_Rank'].iloc[0]

        last_month_quantity = stock_data_flt.groupby('Ticker')['Quantity'].last().to_dict()
        last_month_value = stock_data_flt.groupby('Ticker')['Buy_Hold_Value'].last().to_dict()
        stock_data_flt['Total_Portfolio_Value'] = stock_data_flt.groupby('Date')['Buy_Hold_Value'].transform('sum')
        df_lis.append(stock_data_flt)

    return pd.concat(df_lis, ignore_index=True) if df_lis else pd.DataFrame()

# --- Hedge Book Utilities ---
def _build_hedge_segment(hedge_prices, start_date, end_date, base_values, segment_name):
    """
    Helper to value a specific hedge allocation over a period.
    """
    segment = hedge_prices[
        (hedge_prices['Date'] >= start_date) & (hedge_prices['Date'] <= end_date) & (hedge_prices['Ticker'].isin(base_values))
    ][['Date', 'Ticker', 'Open', 'Close']].copy()
    if segment.empty: return segment

    segment = segment.sort_values(['Ticker', 'Date'])
    segment['%change'] = segment.groupby('Ticker')['Close'].pct_change()
    segment['Initial_Allocation'] = segment['Ticker'].map(base_values)
    segment['ret_factor'] = 1 + segment['%change'].fillna(0)
    segment['cum_factor'] = segment.groupby('Ticker')['ret_factor'].cumprod()
    segment['Buy_Hold_Value'] = segment['Initial_Allocation'] * segment['cum_factor']

    buy_prices = segment.groupby('Ticker')['Close'].transform('first')
    segment['Buy_Price'] = buy_prices
    segment['Quantity'] = np.where(buy_prices > 0, segment['Initial_Allocation'] / buy_prices, 0.0)
    segment['Selection_Date'] = start_date
    segment['Hedge_Segment'] = segment_name
    segment['Total_Portfolio_Value'] = segment.groupby('Date')['Buy_Hold_Value'].transform('sum')
    return segment.drop(columns=['ret_factor', 'cum_factor'])

def build_rebalanced_hedge_book(base_portfolio_df, portfolio_end_date=None, default_hedge_value=25.0):
    """
    Constructs the entire history of hedge assets with transitions (Dec, Feb, Mar, May).
    """
    if portfolio_end_date is None:
        portfolio_end_date = pd.to_datetime(base_portfolio_df['Date']).max()
    else:
        portfolio_end_date = pd.to_datetime(portfolio_end_date)

    cutoff_date = pd.Timestamp('2025-11-30')
    if portfolio_end_date <= cutoff_date:
        return pd.DataFrame()

    hedge_start_factor = base_portfolio_df[
        (base_portfolio_df['Ticker'] == 'GOLDBEES') & (base_portfolio_df['Date'] <= cutoff_date)
    ].sort_values('Date')
    hedge_seed = float(hedge_start_factor['Buy_Hold_Value'].iloc[-1]) if not hedge_start_factor.empty else default_hedge_value

    logger.info("Fetching hedge asset historical data...")
    hedge_tickers = ['GOLDBEES', 'SILVERBEES', 'MOGSEC', 'LIQUIDCASE', 'CPSEETF', 'NEXT50IETF']
    hedge_prices, _ = fetch_truedata_history(hedge_tickers, duration='5 Y', bar_size='EOD')

    segments = []

    # Leg 1: Dec-Jan (60/20/20)
    dec_s = pd.Timestamp('2025-12-01')
    jan_e = min(pd.Timestamp('2026-01-31'), portfolio_end_date)
    if portfolio_end_date >= dec_s:
        df_dj = _build_hedge_segment(hedge_prices, dec_s, jan_e, 
                                     {'GOLDBEES': 0.60 * hedge_seed, 'SILVERBEES': 0.20 * hedge_seed, 'MOGSEC': 0.20 * hedge_seed}, 
                                     '2025-12_to_2026-01')
        if not df_dj.empty: segments.append(df_dj)
    else: df_dj = pd.DataFrame()

    # Leg 2: Feb (40/60)
    feb_s = pd.Timestamp('2026-02-01')
    feb_e = min(pd.Timestamp('2026-02-28'), portfolio_end_date)
    if portfolio_end_date >= feb_s and not df_dj.empty:
        feb_val = df_dj.groupby('Date')['Buy_Hold_Value'].sum().iloc[-1]
        df_f = _build_hedge_segment(hedge_prices, feb_s, feb_e, 
                                    {'GOLDBEES': 0.40 * feb_val, 'MOGSEC': 0.60 * feb_val}, 
                                    '2026-02')
        if not df_f.empty: segments.append(df_f)
    else: df_f = pd.DataFrame()

    # Leg 3: Mar-Apr (Gold/LiquidCase)
    mar_s = pd.Timestamp('2026-03-01')
    apr_e = min(pd.Timestamp('2026-04-30'), portfolio_end_date)
    if portfolio_end_date >= mar_s and not df_f.empty:
        last_vals = df_f[df_f['Date'] == df_f['Date'].max()].set_index('Ticker')['Buy_Hold_Value']
        df_ma = _build_hedge_segment(hedge_prices, mar_s, apr_e, 
                                     {'GOLDBEES': last_vals.get('GOLDBEES', 0.0), 'LIQUIDCASE': last_vals.get('MOGSEC', 0.0)}, 
                                     '2026-03_to_04')
        if not df_ma.empty: segments.append(df_ma)
    else: df_ma = pd.DataFrame()

    # Leg 4: May-2026 onwards (Specific May Rebalance)
    may_s = pd.Timestamp('2026-05-01')
    if portfolio_end_date >= may_s and not df_ma.empty:
        last_vals = df_ma[df_ma['Date'] == df_ma['Date'].max()].set_index('Ticker')['Buy_Hold_Value']
        total_hedge = last_vals.sum()
        
        # 25% Allocation Split: 10% LiquidCase, 5% GoldBees, 5% CPSEETF, 5% NEXT50IETF
        may_values = {
            'LIQUIDCASE': (10/25) * total_hedge,
            'GOLDBEES':   (5/25)  * total_hedge,
            'CPSEETF':    (5/25)  * total_hedge,
            'NEXT50IETF': (5/25)  * total_hedge
        }
        df_may = _build_hedge_segment(hedge_prices, may_s, portfolio_end_date, may_values, '2026-05_onward')
        if not df_may.empty: segments.append(df_may)

    return pd.concat(segments, ignore_index=True) if segments else pd.DataFrame()

# --- Main Pipeline Execution ---
def prepare_and_process_portfolio(input_file, start_date, end_date, output_folder, 
                                  equity_allocation=75, gold_allocation=25):
    """
    Orchestrates the loading of rankings and the valuation of equity and hedge books.
    """
    logger.info(f"Processing portfolio from {input_file}...")
    nav_df_raw = pd.read_excel(input_file).rename(columns={'End_Date': 'Date'})
    nav_df_raw['Date'] = pd.to_datetime(nav_df_raw['Date'])

    selected_cols = ['Date', 'Ticker']
    if 'Real_Rank' in nav_df_raw.columns:
        selected_cols.append('Real_Rank')

    nav_df = nav_df_raw[(nav_df_raw['Date'] >= start_date) & (nav_df_raw['Date'] <= end_date)].reset_index(drop=True)[selected_cols]
    nav_df['Year-Month'] = nav_df['Date'].dt.to_period('M').astype(str)

    # Initial Gold entry (for the baseline before rebalancing logic kicks in)
    gold_seeds = pd.DataFrame({'Date': nav_df['Date'].unique(), 'Ticker': 'GOLDBEES', 'Year-Month': nav_df['Year-Month'].unique()})
    if 'Real_Rank' in nav_df.columns: gold_seeds['Real_Rank'] = np.nan

    # Fetch Data for Equity
    equity_tickers = nav_df['Ticker'].unique()
    equity_data, _ = fetch_truedata_history(equity_tickers, duration='10 Y')

    # Fetch Data for Baseline Gold
    gold_data, _ = fetch_truedata_history(['GOLDBEES'], duration='10 Y')

    # Value Equity & Baseline Gold
    final_equity = process_portfolio(nav_df, equity_data, equity_allocation, inception_date=start_date)
    final_gold_base = process_portfolio(gold_seeds, gold_data, gold_allocation, inception_date=start_date)

    combined_base = pd.concat([final_equity, final_gold_base], ignore_index=True).sort_values(['Date', 'Ticker'])
    
    # Build Rebalanced Hedge Book (Overwrites baseline gold when relevant)
    hedge_book = build_rebalanced_hedge_book(combined_base)
    
    if not hedge_book.empty:
        # Merge hedge book into base portfolio
        hedge_dates = hedge_book['Date'].unique()
        final_base_filtered = combined_base[~( (combined_base['Ticker'] == 'GOLDBEES') & (combined_base['Date'].isin(hedge_dates)) )]
        final_portfolio = pd.concat([final_base_filtered, hedge_book], ignore_index=True).sort_values(['Date', 'Ticker'])
    else:
        final_portfolio = combined_base

    os.makedirs(output_folder, exist_ok=True)
    # Align filenames with main.py expectations
    output_path = os.path.join(output_folder, "Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx")
    maxfolio_path = os.path.join(output_folder, "Momentum_Maxfolio.xlsx")
    
    safe_save_excel(final_portfolio, output_path)
    safe_save_excel(final_portfolio, maxfolio_path) # Also save as Maxfolio

    # --- NAV Comparison vs Benchmark (Nov 11, 2025 onwards) ---
    logger.info("Generating NAV comparison vs Benchmark starting Nov 11, 2025...")
    start_bench = pd.Timestamp('2025-11-11')
    
    # 1. Portfolio Daily Value
    port_daily = final_portfolio.groupby('Date')['Buy_Hold_Value'].sum().reset_index()
    port_daily = port_daily[port_daily['Date'] >= start_bench].sort_values('Date')
    
    if not port_daily.empty:
        # Normalize Portfolio
        initial_port_val = port_daily['Buy_Hold_Value'].iloc[0]
        port_daily['PORT NAV'] = (port_daily['Buy_Hold_Value'] / initial_port_val) * 100
        
        # 2. Benchmark (BSE500)
        bench_ticker = 'BSE500'
        bench_data, _ = fetch_truedata_history([bench_ticker], duration='2 Y', bar_size='EOD')
        
        if not bench_data.empty:
            bench_data = bench_data[['Date', 'Close']].rename(columns={'Close': 'BM_Price'})
            bench_data = bench_data[bench_data['Date'] >= start_bench].sort_values('Date')
            
            if not bench_data.empty:
                initial_bm_price = bench_data['BM_Price'].iloc[0]
                bench_data['BM NAV'] = (bench_data['BM_Price'] / initial_bm_price) * 100
                
                # Merge
                nav_comp = pd.merge(port_daily[['Date', 'PORT NAV']], 
                                    bench_data[['Date', 'BM NAV']], 
                                    on='Date', how='inner')
                
                nav_comp_path = os.path.join(output_folder, "NAV.xlsx")
                safe_save_excel(nav_comp, nav_comp_path)
                logger.info(f"NAV comparison saved to: {nav_comp_path}")

    return final_portfolio

if __name__ == "__main__":
    START_DATE = "2023-04-01"
    END_DATE   = datetime.now().strftime("%Y-%m-%d") # Or "2026-05-01"

    # Step 1: Run Momentum Strategy (Generate Rankings)
    # This will create files in Momentum_Results/Nifty_500_2025_20_stocks_results/
    master_summary_path = run_momentum_strategy(
        universe_file = str(UNIVERSE),
        start_date    = "2022-10-01", # Need buffer for first 6-month window
        end_date      = END_DATE,
        top_n         = 20
    )

    if master_summary_path:
        # Step 2: Process Portfolio Valuation
        prepare_and_process_portfolio(
            input_file        = master_summary_path,
            start_date        = START_DATE,
            end_date          = END_DATE,
            output_folder     = str(DATA_DIR),
            equity_allocation = 75,
            gold_allocation   = 25
        )
    else:
        logger.error("Failed to generate master momentum summary. Portfolio processing skipped.")