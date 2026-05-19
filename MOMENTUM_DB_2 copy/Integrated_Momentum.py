import gc
import multiprocessing
import os
import sys

import time
import logging
import pandas as pd
from truedata import TD_hist

def fetch_truedata_history(
    username: str,
    password: str,
    ticker_list: list,
    duration: str = '1 Y',
    bar_size: str = 'EOD',
    sleep_time: float = 0.1
) -> tuple[pd.DataFrame, list]:
    """
    Fetches historical data from TrueData for a list of tickers.

    Parameters
    ----------
    username : str
        TrueData username.
    password : str
        TrueData password.
    ticker_list : list
        List of ticker symbols to fetch data for.
    duration : str, optional
        Duration of data (e.g., '1 Y', '25 Y', etc.). Default is '1 Y'.
    bar_size : str, optional
        Bar size for data ('EOD', 'WEEK', etc.). Default is 'EOD'.
    sleep_time : float, optional
        Delay between API calls to avoid throttling. Default is 0.2 seconds.

    Returns
    -------
    final_df : pd.DataFrame
        Combined DataFrame of all tickers' historical data.
    error_list : list
        List of tickers that failed to fetch.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # Initialize connection
    td_hist = TD_hist(username, password)

    df_list = []
    error_list = []

    for ticker in ticker_list:
        try:
            df = td_hist.get_historic_data([ticker], duration=duration, bar_size=bar_size)

            df['Ticker'] = ticker
            df = df.rename(columns={
                'timestamp': 'Date',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'open': 'Open'
            })

            df_list.append(df)
            logging.info(f"Fetched data for {ticker} ({len(df)} rows).")
            time.sleep(sleep_time)

        except Exception as e:
            logging.error(f"Failed to fetch data for {ticker}: {e}")
            error_list.append(ticker)

    final_df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    return final_df, error_list


gc.collect()

import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import yfinance as yf
from pathlib import Path

import os

def run_momentum_strategy(universe_file: str,
                          start_date: str,
                          end_date: str,
                          top_n: int,
                          output_root: str = "Momentum_Results") -> str:
    """
    Run rolling-window momentum strategy on given stock universe.

    Parameters
    ----------
    universe_file : str
        Path to universe file (.csv or .xlsx) with columns ["Symbol", "ISIN Code"].
    start_date : str
        Start date for backtest (YYYY-MM-DD).
    end_date : str
        End date for backtest (YYYY-MM-DD).
    top_n : int
        Number of top ranked stocks to select each window.
    output_root : str
        Root folder where results will be saved.

    Returns
    -------
    str
        Path to master summary file.
    """


    # ==== 1. Load Universe ====
    if universe_file.endswith(".csv"):
        stock_list = pd.read_csv(universe_file)[["Symbol", "ISIN Code"]]
    else:
        stock_list = pd.read_excel(universe_file)[["Symbol", "ISIN Code"]]
    # username = 'tdwsf695'
    # password = 'ocean@695'
    
    username = 'tdwsf695'
    password = 'ocean@695'
    # username = 'td105'
    # password = 'sharma@105'
    # stock_list["Ticker"] = stock_list["Symbol"] + ".NS"
    stock_list["Ticker"] = stock_list["Symbol"] 
    symbol_list = stock_list["Symbol"].tolist()
    universe_name = Path(universe_file).stem
    output_dir = os.path.join(output_root, f"{universe_name}_{top_n}_stocks_results")
    os.makedirs(output_dir, exist_ok=True)

    # ==== 2. Download Data ====
    total_start = pd.to_datetime(start_date)
    total_end = pd.to_datetime(end_date)

    print(f"\n📥 Downloading price data for {len(symbol_list)} symbols...")
    # data = yf.download(symbol_list, start=total_start.strftime('%Y-%m-%d'),
    #                    end=total_end.strftime('%Y-%m-%d'), progress=True)
    # prices_all = data["Close"]
    # prices_all.index = pd.to_datetime(prices_all.index)
    # print("✅ Download complete.")

    data, errors = fetch_truedata_history(username, password, symbol_list, duration='10 Y', bar_size='EOD')
    data = data[['Date', 'Close', 'Ticker']]
    data.drop_duplicates(subset=['Date', 'Ticker'], inplace=True)
    print(data)
    print("Failed tickers:", errors)
    prices = data.pivot(index="Date", columns="Ticker", values="Close")  
    # optional: sort by date
    prices_all = prices.sort_index()



    # ==== 3. Create Rolling Windows ====
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

    print(f"📊 Created {len(windows)} rolling windows.")

    # ==== 4. Process Each Window ====
    for start, end, prices in windows:
        file_suffix = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        print(f"\n🔍 Processing window: {start.date()} → {end.date()}")

        prices.dropna(axis=1, how='all', inplace=True)
        if prices.empty:
            print("⚠️ All price data missing. Skipping window.")
            continue

        # Monthly momentum
        monthclose = prices.groupby(prices.index.strftime('%Y-%m')).tail(1)
        monthstart = prices.groupby(prices.index.strftime('%Y-%m')).head(1)
        monthstart.index = monthclose.index
        monchange = (monthclose - monthstart) / monthstart
        MOM = (monchange + 1).product() - 1
        mom = MOM * 100

        # Daily returns
        daily_ret = prices.pct_change(fill_method=None)
        positivechange = (daily_ret[daily_ret > 0].count() / daily_ret.count()) * 100
        negativechange = (daily_ret[daily_ret < 0].count() / daily_ret.count()) * 100

        result = pd.concat([positivechange, negativechange, mom], axis=1, join='inner')
        result.columns = ["Positive", "Negative", "Momentum"]
        result = result.reset_index().rename(columns={'index': 'Ticker'})

        # Merge ISIN
        result = pd.merge(result, stock_list[["Ticker", "ISIN Code"]], on="Ticker", how="left")

        # Ranking
        df = result.copy()
        df["Rank_Mom"] = df["Momentum"].rank(method='min', ascending=False)
        print('rank df:', df)
        df['FIP'] = df.apply(lambda row: row['Negative'] - row['Positive'] if row['Momentum'] > 0 else np.nan, axis=1)
        # df['FIP'] = df.apply(lambda row: row['Negative'] - row['Positive'])

        df.dropna(inplace=True)
        df["FIP_rank"] = df["FIP"].rank(method="first", ascending=True)
        df["Combined_Rank"] = df["Rank_Mom"] + df["FIP_rank"]
        if end.strftime('%Y-%m-%d') == '2026-01-01':
            df = df[~(df['Ticker'].isin(['MARUTI', 'PTCIL']))]

        # Sort by rank
        df = df.sort_values(by="Combined_Rank", ascending=True)

        # Apply CMP filter
        last_close = prices.iloc[-1]  # Series: Ticker -> last close price
        df["CMP"] = df["Ticker"].map(last_close)
        
        before_filter = len(df)
        # Filter out stocks with CMP > 7500 (also filters out NaN CMP)
        df = df[df["CMP"] <= 7500].copy()
        
        filtered_out = before_filter - len(df)
        if filtered_out > 0:
            print(f"🚫 Filtered out {filtered_out} stock(s) with CMP > ₹7,500")

        # Take top N after filtering
        df = df.head(top_n).copy()
        df["Real_Rank"] = range(1, len(df) + 1)
        df["End_Date"] = end.strftime('%Y-%m-%d')

        # Save each window
        output_file = os.path.join(output_dir, f"momentum_{file_suffix}.xlsx")
        df.to_excel(output_file, index=False)
        print(f"✅ Saved results to: {output_file}")

    # ==== 5. Master File ====
    print("\n📂 Creating master summary file...")
    master_data = []
    for file in os.listdir(output_dir):
        if file.startswith("momentum_") and file.endswith(".xlsx"):
            df = pd.read_excel(os.path.join(output_dir, file))
            selected_df = df[["End_Date", "ISIN Code", "Ticker", 'Real_Rank']].copy()
            master_data.append(selected_df)

    if master_data:
        master_df = pd.concat(master_data, ignore_index=True)
        master_file_path = os.path.join(output_dir, "master_momentum_summary.xlsx")
        master_df.to_excel(master_file_path, index=False)
        print(f"✅ Master file saved to: {master_file_path}")
        return master_file_path
    else:
        print("⚠️ No window files found, master not created.")
        return None


gc.collect()



# Momentum/Automating Momentum/Universe/Nifty_500_2025_Apr.csv
# "C:\Users\Admin\Momentum\Automating Momentum\Universe\Nifty_500_2025_Apr.csv"
master_file = run_momentum_strategy(
    universe_file=r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Universe\Nifty_500_2025_Apr.csv",
    start_date="2022-06-01",
    end_date="2026-04-01",
    top_n=20,
    output_root="Stocks"
)
print("Master summary located at:", master_file)

gc.collect()

# ----------------xxxxxxxxxxxxxxx---------------------------------------

gc.collect()

import sys
os.system(f"{sys.executable} -m pip install pyodbc")
import numpy as np
import pandas as pd
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import yfinance as yf
import pyodbc
os.system(f"{sys.executable} -m pip install matplotlib")
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')
import time
import logging
import pandas as pd
from truedata import TD_hist
import requests



gc.collect()

def fetch_truedata_history(
    ticker_list: list,
    duration: str = '1 Y',
    bar_size: str = 'EOD',
    sleep_time: float = 0.1
) -> tuple[pd.DataFrame, list]:
    """
    Fetches historical data from TrueData for a list of tickers.

    Parameters
    ----------
    username : str
        TrueData username.
    password : str
        TrueData password.
    ticker_list : list
        List of ticker symbols to fetch data for.
    duration : str, optional
        Duration of data (e.g., '1 Y', '25 Y', etc.). Default is '1 Y'.
    bar_size : str, optional
        Bar size for data ('EOD', 'WEEK', etc.). Default is 'EOD'.
    sleep_time : float, optional
        Delay between API calls to avoid throttling. Default is 0.2 seconds.

    Returns
    -------
    final_df : pd.DataFrame
        Combined DataFrame of all tickers' historical data.
    error_list : list
        List of tickers that failed to fetch.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    username = 'tdwsf695'
    password = 'ocean@695'
    # Initialize connection
    td_hist = TD_hist(username, password)
    df_list = []
    error_list = []
    for ticker in ticker_list:
        try:
            df = td_hist.get_historic_data([ticker], duration=duration, bar_size=bar_size)

            df['Ticker'] = ticker
            # Check column names and rename accordingly
            rename_dict = {}
            if 'timestamp' in df.columns:
                rename_dict['timestamp'] = 'Date'
            elif 'datetime' in df.columns:
                rename_dict['datetime'] = 'Date'
            elif 'date' in df.columns:
                rename_dict['date'] = 'Date'
            rename_dict.update({
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'open': 'Open'
            })
            df = df.rename(columns=rename_dict)

            df_list.append(df)
            logging.info(f"Fetched data for {ticker} ({len(df)} rows).")
            time.sleep(sleep_time)

        except Exception as e:
            logging.error(f"Failed to fetch data for {ticker}: {e}")
            error_list.append(ticker)

    final_df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    return final_df, error_list



gc.collect()

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

def process_portfolio(nav_df, ticker_data, initial_value=75, inception_date=None, output_file=None):
    """
    Process portfolio allocation with month-by-month rebalancing.

    Parameters
    ----------
    nav_df : pd.DataFrame
        Dataframe with at least ['Date', 'Year-Month', 'Ticker'] columns.
    ticker_data : pd.DataFrame
        Historical OHLC data with ['Date', 'Ticker', 'Close'].
    initial_value : float
        Initial portfolio allocation value.
    inception_date : str or pd.Timestamp or None
        Start date from which holdings should be valued.
    output_file : str or None
        If provided, saves the final dataframe to Excel.

    Returns
    -------
    pd.DataFrame
        Final dataframe with portfolio values.
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
            (ticker_data['Date'] >= prev_month_start)
            & (ticker_data['Date'] <= curr_month_end)
            & (ticker_data['Ticker'].isin(tickers))
        ].copy()
        stock_data = stock_data[stock_data['Date'] >= inception_date].copy()
        stock_data['%change'] = stock_data.groupby('Ticker')['Close'].pct_change()

        stock_data_flt = stock_data[
            (stock_data['Date'] >= curr_month_start) & (stock_data['Date'] <= curr_month_end)
        ].copy()
        if stock_data_flt.empty:
            continue

        if not last_month_value:
            allocation_per_stock = initial_value / len(tickers)
            stock_allocations = {ticker: allocation_per_stock for ticker in tickers}
        else:
            stock_allocations = {ticker: last_month_value[ticker] for ticker in tickers if ticker in last_month_value}
            dropped_stocks = [ticker for ticker in last_month_value if ticker not in tickers]
            dropped_value = sum(last_month_value[ticker] for ticker in dropped_stocks)
            new_stocks = [ticker for ticker in tickers if ticker not in last_month_value]
            if new_stocks:
                allocation_per_stock = dropped_value / len(new_stocks) if dropped_value else 0.0
                for ticker in new_stocks:
                    stock_allocations[ticker] = allocation_per_stock

        for ticker, init_value in stock_allocations.items():
            ticker_index = stock_data_flt[stock_data_flt['Ticker'] == ticker].index
            ticker_df = stock_data_flt.loc[ticker_index].copy()
            if ticker_df.empty:
                continue

            stock_data_flt.loc[ticker_index, 'Initial_Allocation'] = init_value
            stock_data_flt.loc[ticker_index, 'Selection_Date'] = selection_date
            stock_data_flt.loc[ticker_index, 'Buy_Hold_Value'] = init_value * (
                (1 + stock_data_flt.loc[ticker_index, '%change'].fillna(0)).cumprod()
            )

            buy_price = float(ticker_df.iloc[0]['Close'])
            quantity = last_month_quantity.get(ticker, init_value / buy_price if buy_price else 0.0)
            stock_data_flt.loc[ticker_index, 'Buy_Price'] = buy_price
            stock_data_flt.loc[ticker_index, 'Quantity'] = quantity
            if 'Real_Rank' in month_nav.columns:
                stock_data_flt.loc[ticker_index, 'Real_Rank'] = month_nav.loc[month_nav['Ticker'] == ticker, 'Real_Rank'].iloc[0]

        last_month_quantity = stock_data_flt.groupby('Ticker')['Quantity'].last().to_dict()
        last_month_value = stock_data_flt.groupby('Ticker')['Buy_Hold_Value'].last().to_dict()
        stock_data_flt['Total_Portfolio_Value'] = stock_data_flt.groupby('Date')['Buy_Hold_Value'].transform('sum')
        df_lis.append(stock_data_flt)

    final_df = pd.concat(df_lis, ignore_index=True).sort_values(['Date', 'Ticker']).reset_index(drop=True)

    if output_file:
        final_df.to_excel(output_file, index=False)

    return final_df


def build_weighted_hedge_segment(hedge_prices, start_date, end_date, base_values, segment_name):
    segment = hedge_prices[
        (hedge_prices['Date'] >= start_date)
        & (hedge_prices['Date'] <= end_date)
        & (hedge_prices['Ticker'].isin(base_values))
    ][['Date', 'Ticker', 'Open', 'Close']].copy()
    if segment.empty:
        return segment

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

    hedge_prices = fetch_truedata_history(
        ticker_list=['GOLDBEES', 'SILVERBEES', 'MOGSEC', 'LIQUIDCASE'],
        duration='5 Y',
        bar_size='EOD',
        sleep_time=0.1
    )[0]

    segments = []

    decjan_start = pd.Timestamp('2025-12-01')
    decjan_end = min(pd.Timestamp('2026-01-31'), portfolio_end_date)
    if portfolio_end_date >= decjan_start:
        decjan_values = {'GOLDBEES': 0.60 * hedge_seed, 'SILVERBEES': 0.20 * hedge_seed, 'MOGSEC': 0.20 * hedge_seed}
        df_decjan = build_weighted_hedge_segment(
            hedge_prices,
            start_date=decjan_start,
            end_date=decjan_end,
            base_values=decjan_values,
            segment_name='2025-12_to_2026-01'
        )
        if not df_decjan.empty:
            segments.append(df_decjan)
        else:
            df_decjan = pd.DataFrame()
    else:
        df_decjan = pd.DataFrame()

    feb_start = pd.Timestamp('2026-02-01')
    feb_end = min(pd.Timestamp('2026-02-28'), portfolio_end_date)
    if portfolio_end_date >= feb_start and not df_decjan.empty:
        feb_factor = (
            df_decjan.groupby('Date', as_index=False)['Buy_Hold_Value'].sum().sort_values('Date')['Buy_Hold_Value'].iloc[-1]
        )
        feb_values = {'GOLDBEES': 0.40 * feb_factor, 'MOGSEC': 0.60 * feb_factor}
        df_feb = build_weighted_hedge_segment(
            hedge_prices,
            start_date=feb_start,
            end_date=feb_end,
            base_values=feb_values,
            segment_name='2026-02'
        )
        if not df_feb.empty:
            segments.append(df_feb)
        else:
            df_feb = pd.DataFrame()
    else:
        df_feb = pd.DataFrame()

    mar_start = pd.Timestamp('2026-03-01')
    if portfolio_end_date >= mar_start and not df_feb.empty:
        feb_last_date = df_feb['Date'].max()
        feb_last = df_feb[df_feb['Date'] == feb_last_date].set_index('Ticker')['Buy_Hold_Value'].to_dict()
        mar_values = {'GOLDBEES': feb_last.get('GOLDBEES', 0.0), 'LIQUIDCASE': feb_last.get('MOGSEC', 0.0)}
        df_mar = build_weighted_hedge_segment(
            hedge_prices,
            start_date=mar_start,
            end_date=portfolio_end_date,
            base_values=mar_values,
            segment_name='2026-03_onward'
        )
        if not df_mar.empty:
            segments.append(df_mar)

    if not segments:
        return pd.DataFrame()

    return pd.concat(segments, ignore_index=True).sort_values(['Date', 'Ticker']).reset_index(drop=True)

gc.collect()

import os
import pandas as pd

def prepare_and_process_portfolio(input_file, start_date, end_date, output_folder,
                                  process_portfolio,
                                  equity_allocation=75, gold_allocation=25):
    """
    Prepare portfolio dataframe with momentum stocks + GOLDBEES and process performance.
    """

    nav_df_raw = pd.read_excel(input_file).rename(columns={'End_Date': 'Date'})
    nav_df_raw['Date'] = pd.to_datetime(nav_df_raw['Date'])

    selected_cols = ['Date', 'Ticker']
    if 'Real_Rank' in nav_df_raw.columns:
        selected_cols.append('Real_Rank')

    nav_df = (
        nav_df_raw[(nav_df_raw['Date'] >= start_date) & (nav_df_raw['Date'] <= end_date)]
        .reset_index(drop=True)[selected_cols]
    )
    nav_df['Year-Month'] = nav_df['Date'].dt.to_period('M').astype(str)

    goldbees_df = pd.DataFrame({
        'Date': nav_df['Date'].drop_duplicates().sort_values(),
        'Ticker': 'GOLDBEES'
    })
    if 'Real_Rank' in nav_df.columns:
        goldbees_df['Real_Rank'] = np.nan
    goldbees_df['Year-Month'] = pd.to_datetime(goldbees_df['Date']).dt.to_period('M').astype(str)

    concat_df = (
        pd.concat([nav_df, goldbees_df], ignore_index=True)
          .sort_values(['Date', 'Ticker'])
          .reset_index(drop=True)
    )

    ticker_df = concat_df.query("Ticker != 'GOLDBEES'")
    symbol_list = ticker_df['Ticker'].unique()
    ticker_data_other_stocks = fetch_truedata_history(
        ticker_list=symbol_list,
        duration='10 Y',
        bar_size='EOD',
        sleep_time=0.1
    )[0]

    gold_df = concat_df.query("Ticker == 'GOLDBEES'")
    symbol_list = gold_df['Ticker'].unique()
    ticker_data_gold = fetch_truedata_history(
        ticker_list=symbol_list,
        duration='10 Y',
        bar_size='EOD',
        sleep_time=0.1
    )[0]

    inception_date = pd.to_datetime(start_date)
    final_df_other_stocks = process_portfolio(
        ticker_df,
        ticker_data_other_stocks,
        equity_allocation,
        inception_date=inception_date
    )
    final_df_gold = process_portfolio(
        gold_df,
        ticker_data_gold,
        gold_allocation,
        inception_date=inception_date
    )

    final_df = (
        pd.concat([final_df_other_stocks, final_df_gold], ignore_index=True)
          .sort_values(['Date', 'Ticker'])
          .reset_index(drop=True)
    )

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    middle_folder = os.path.basename(os.path.dirname(input_file))
    output_file = os.path.join(output_folder, f"{middle_folder}_gold_buy&hold_returns.xlsx")
    print(f"Final output path: {output_file}")

    return final_df

gc.collect()

final_df = prepare_and_process_portfolio(
    input_file=r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Stocks\Nifty_500_2025_Apr_20_stocks_results\master_momentum_summary.xlsx",
    start_date="2023-04-01",
    end_date=date.today().strftime('%Y-%m-%d'),
    output_folder="Trials",
    process_portfolio=process_portfolio
)

final_df

gc.collect()

old_df = final_df[~((final_df['Date']>'2025-11-30') & (final_df['Ticker']=='GOLDBEES'))]
old_df



gc.collect()

np.sort(old_df['Ticker'].unique())



gc.collect()

# Build hedge book with the same monthly rebalancing rules used in the script
portfolio_end_date = pd.to_datetime(final_df['Date']).max()
df = build_rebalanced_hedge_book(
    base_portfolio_df=final_df,
    portfolio_end_date=portfolio_end_date,
    default_hedge_value=25.0
 )
df

gc.collect()

# Hedge dataframe is already built in previous cell
df[['Date', 'Ticker', 'Buy_Hold_Value']].head()

gc.collect()

# No-op: valuation already computed in hedge builder cell
df.tail()

gc.collect()

conc_df = pd.concat([old_df, df])
conc_df



gc.collect()

import sys
os.system(f'"{sys.executable}" -m pip install plotly')
import sys
os.system(f'"{sys.executable}" -m pip install nbformat --upgrade')
import plotly.express as px

# âœ… Group by Date and calculate total portfolio value
portfolio_summary = (
    conc_df.groupby("Date", as_index=False)["Buy_Hold_Value"].sum()
)
# âœ… Plot with Plotly
fig = px.line(
    portfolio_summary,
    x="Date",
    y="Buy_Hold_Value",
    title="Buy_Hold_Value Over Time",
    labels={"Date": "Date", "Buy_Hold_Value": "Buy_Hold_Value"},
    markers=True
)

fig.update_traces(line=dict(width=2))
fig.update_layout(width=1000,   # ðŸ”‘ width
                  height=500)    # ðŸ”‘ height
import plotly.io as pio
pio.renderers.default = "browser"
fig.show()



gc.collect()

# Momentum/Automating Momentum True Data/Trials/Nifty_500_2025_Apr_20_stocks_results_GoldSilverDebt_buy&hold_returns.xlsx



gc.collect()

conc_df.to_excel(r'C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx', index=True)
# \Trials



gc.collect()

nse = fetch_truedata_history(
    ticker_list = ['BSE500'],
    duration = '5 Y',
    bar_size = 'EOD',
    sleep_time= 0.1
)[0]
nse = nse[["Date", "Close"]].rename(columns={'Close':'Buy_Hold_Value'})
nse['%change'] = nse['Buy_Hold_Value'].pct_change()
nse = nse[nse['Date'] >= '2023-04-01']
nse.to_excel('Trials\\nse500_Nifty_500_2025_Apr_nse500_nse500_nse500_nse500_nse500_returns.xlsx', index=False)
nse



gc.collect()

conc_df




gc.collect()

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import pytz
import yfinance as yf
import pyodbc
import matplotlib.pyplot as plt
import warnings
warnings.filterwarnings('ignore')
import time
import logging
import pandas as pd
from truedata import TD_hist

gc.collect()

def fetch_truedata_history(
    ticker_list: list,
    duration: str = '1 Y',
    bar_size: str = 'EOD',
    sleep_time: float = 0.1
) -> tuple[pd.DataFrame, list]:
    """
    Fetches historical data from TrueData for a list of tickers.

    Parameters
    ----------
    username : str
        TrueData username.
    password : str
        TrueData password.
    ticker_list : list
        List of ticker symbols to fetch data for.
    duration : str, optional
        Duration of data (e.g., '1 Y', '25 Y', etc.). Default is '1 Y'.
    bar_size : str, optional
        Bar size for data ('EOD', 'WEEK', etc.). Default is 'EOD'.
    sleep_time : float, optional
        Delay between API calls to avoid throttling. Default is 0.2 seconds.

    Returns
    -------
    final_df : pd.DataFrame
        Combined DataFrame of all tickers' historical data.
    error_list : list
        List of tickers that failed to fetch.
    """
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    username =  'tdwsf695'
    password = 'ocean@695'
    # Initialize connection
    td_hist = TD_hist(username, password)
    df_list = []
    error_list = []
    for ticker in ticker_list:
        try:
            df = td_hist.get_historic_data([ticker], duration=duration, bar_size=bar_size)

            df['Ticker'] = ticker
            df = df.rename(columns={
                'timestamp': 'Date',
                'high': 'High',
                'low': 'Low',
                'close': 'Close',
                'open': 'Open'
            })

            df_list.append(df)
            logging.info(f"Fetched data for {ticker} ({len(df)} rows).")
            time.sleep(sleep_time)

        except Exception as e:
            logging.error(f"Failed to fetch data for {ticker}: {e}")
            error_list.append(ticker)

    final_df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()
    return final_df, error_list


gc.collect()

import numpy as np
import pandas as pd
from dateutil.relativedelta import relativedelta

def process_portfolio(nav_df, ticker_data, initial_value=75, output_file=None):
    """
    Process portfolio allocation and returns final dataframe with portfolio performance.

    Parameters
    ----------
    nav_df : pd.DataFrame
        Dataframe with at least ['Year-Month', 'Ticker'] columns.
    get_individual_stock_data : function
        Function to fetch OHLC data. Must accept (tickers, start_date, end_date) and return DataFrame with ['Date','Ticker','Close'].
    initial_value : float
        Initial portfolio allocation value (default=75).
    debt_ticker : str
        Ticker used as debt/alternative asset (default 'MOGSEC.NS').
    output_file : str or None
        If provided, saves the final dataframe to Excel.

    Returns
    -------
    pd.DataFrame
        Final dataframe with portfolio values.
    """
    df_lis = []
    last_month_value = {}
    last_month_quantity = {}

    year_months = nav_df['Year-Month'].unique()
    for i, year_month in enumerate(year_months):
        print(f"\nProcessing: {year_month}")
        print("Last Month Value:", last_month_value)

        tickers = nav_df[nav_df['Year-Month'] == year_month]['Ticker'].unique()
        year_month_date = pd.to_datetime(f"{year_month}-01")


        prev_month_start = (year_month_date - relativedelta(months=2)).strftime('%Y-%m-%d')
        curr_month_start = year_month_date.strftime('%Y-%m-%d')
        curr_month_end = (year_month_date + pd.offsets.MonthEnd(0)).strftime('%Y-%m-%d')

        # --- Fetch stock data ---
        # stock_data = get_individual_stock_data(tickers, prev_month_start, curr_month_end)
        stock_data = (
            ticker_data[(ticker_data['Date'] >= prev_month_start)
            & (ticker_data['Date'] <= curr_month_end) 
            & (ticker_data['Ticker'].isin(tickers))])
        stock_data = stock_data[stock_data['Date']>='2025-11-11']
        
        # % change
        stock_data['%change'] = stock_data.groupby('Ticker')['Close'].pct_change()
        # Filter current month
        stock_data_flt = stock_data[
            (stock_data['Date'] >= curr_month_start) & (stock_data['Date'] <= curr_month_end)
        ].copy()

        print(stock_data_flt)

        # --- Portfolio allocation logic ---
        if len(last_month_value) == 0:
            # First month → allocate initial portfolio equally
            allocation_per_stock = initial_value / len(tickers)
            stock_allocations = {t: allocation_per_stock for t in tickers}
        else:
            # Continue portfolio
            stock_allocations = {t: last_month_value[t] for t in tickers if t in last_month_value}

            # Pool value of dropped stocks
            dropped_stocks = [t for t in last_month_value if t not in tickers]
            dropped_value = sum(last_month_value[t] for t in dropped_stocks)

            # New stocks → share the dropped value equally
            new_stocks = [t for t in tickers if t not in last_month_value]
            if new_stocks:
                allocation_per_stock = dropped_value / len(new_stocks)
                for t in new_stocks:
                    stock_allocations[t] = allocation_per_stock

        # Apply allocations into dataframe
        for tkr, init_value in stock_allocations.items():
            tkr_idx = stock_data_flt[stock_data_flt['Ticker'] == tkr].index
            stock_data_flt.loc[tkr_idx, 'Buy_Hold_Value'] = init_value * (
                (1 + stock_data_flt.loc[tkr_idx, '%change'].fillna(0)).cumprod()
            )
            
            tkr_df = stock_data_flt[stock_data_flt['Ticker'] == tkr]
            if tkr_df.empty:
                continue

            buy_price = tkr_df.iloc[0]['Close']

            # Carry quantity if stock existed last month
            if tkr in last_month_quantity:
                quantity = last_month_quantity[tkr]
            else:
                quantity = init_value / buy_price
                
            stock_data_flt.loc[tkr_df.index, 'Buy_Price'] = buy_price
            stock_data_flt.loc[tkr_df.index, 'Quantity'] = quantity

        # --- Update last month values ---

        last_month_quantity = (
            stock_data_flt.groupby('Ticker')['Quantity'].last().to_dict()
        )
        
        last_month_value = (
            stock_data_flt.groupby('Ticker')['Buy_Hold_Value'].last().to_dict()
        )

        # --- Track total portfolio value ---
        stock_data_flt['Total_Portfolio_Value'] = (
            stock_data_flt.groupby('Date')['Buy_Hold_Value'].transform('sum')
        )

        df_lis.append(stock_data_flt)

    
    final_df = pd.concat(df_lis).reset_index(drop=True)

    # if output_file:
    #     final_df.to_excel(output_file, index=False)

    return final_df



gc.collect()

import os
import pandas as pd

def prepare_and_process_portfolio(input_file, start_date, end_date, output_folder,
                                  process_portfolio,
                                  equity_allocation=75, gold_allocation=25):
    """
    Prepare portfolio dataframe with momentum stocks + GOLDBEES and process performance.

    Parameters
    ----------
    input_file : str
        Path to momentum Excel file (with End_Date, Ticker columns).
    start_date : str (YYYY-MM-DD)
        Start date for filtering.
    end_date : str (YYYY-MM-DD)
        End date for filtering.
    output_folder : str
        Folder to save output file.
    get_individual_stock_data : function
        Function to fetch stock NAV/price data.
    process_pocrtfolio : function
        Function to process equity portion of portfolio.
    process_gold : function
        Function to process gold portion of portfolio.
    equity_allocation : int, optional
        Initial allocation to equities (default=75000).
    gold_allocation : int, optional
        Initial allocation to gold (default=25000).

    Returns
    -------
    final_df : pd.DataFrame
        Combined portfolio dataframe.
    """

    # Load and clean
    nav_df = pd.read_excel(input_file).rename(columns={'End_Date': 'Date'})
    nav_df['Date'] = pd.to_datetime(nav_df['Date'])
    nav_df = (
        nav_df[(nav_df['Date'] >= start_date) & (nav_df['Date'] <= end_date)]
        .reset_index(drop=True)[['Date', 'Ticker']]
    )
    nav_df['Year-Month'] = nav_df['Date'].dt.to_period('M').astype(str)
    stocks = pd.read_excel(input_file)

    # Add GOLDBEES for each unique date
    goldbees_df = pd.DataFrame({
        'Date': nav_df['Date'].unique(),
        'Ticker': 'GOLDBEES'
    })
    goldbees_df['Year-Month'] = pd.to_datetime(goldbees_df['Date']).dt.to_period('M').astype(str)
    # print(goldbees_df)

    # Combine
    concat_df = (
        pd.concat([nav_df, goldbees_df], ignore_index=True)
          .sort_values(['Date', 'Ticker'])
          .reset_index(drop=True)
    )

    # symbol_list = stocks['Ticker'].unique()
    # ticker_data = fetch_truedata_history(
    #     ticker_list = symbol_list,
    #     duration = '5 Y',
    #     bar_size = 'EOD',
    #     sleep_time= 0.1
    # )[0]
    # final_df = process_portfolio(concat_df, ticker_data, equity_allocation)

    
    # Split
    ticker_df = concat_df.query("Ticker != 'GOLDBEES'")
    symbol_list = ticker_df['Ticker'].unique()
    ticker_data_other_stocks = fetch_truedata_history(
        ticker_list = symbol_list,
        duration = '10 Y',
        bar_size = 'EOD',
        sleep_time= 0.1
    )[0]

    
    gold_df = concat_df.query("Ticker == 'GOLDBEES'")
    symbol_list = gold_df['Ticker'].unique()
    ticker_data_gold = fetch_truedata_history(
        ticker_list = symbol_list,
        duration = '10 Y',
        bar_size = 'EOD',
        sleep_time= 0.1
    )[0]
    # print(gold_df)

    # Process
    final_df_other_stocks = process_portfolio(ticker_df, ticker_data_other_stocks, equity_allocation)
    # final_df_gold = process_gold(gold_df, get_individual_stock_data, gold_allocation)
    final_df_gold = process_portfolio(gold_df, ticker_data_gold, gold_allocation)


    # Merge results
    final_df = (
        pd.concat([final_df_other_stocks, final_df_gold], ignore_index=True)
          .sort_values(['Date', 'Ticker'])
          .reset_index(drop=True)
    )


    # --- ensure output folder exists ---
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    # --- extract middle folder name from input path ---
    middle_folder = os.path.basename(os.path.dirname(input_file))
    # e.g. for path ".../nifty500_21April2025_results/master_momentum_summary.xlsx"
    # middle_folder = "nifty500_21April2025_results"

    # --- create output filename using middle folder ---
    output_file = os.path.join(output_folder, f"{middle_folder}_gold_buy&hold_returns.xlsx")

    # --- save output ---
    # final_df.to_excel(output_file, index=False)
    print(f"✅ Final output saved to: {output_file}")

    return final_df


gc.collect()

#NSE500

gc.collect()

final_df = prepare_and_process_portfolio(
    input_file=r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Stocks\Nifty_500_2025_Apr_20_stocks_results\master_momentum_summary.xlsx",
    start_date="2025-11-11",
    end_date=pd.Timestamp.today().normalize().strftime('%Y-%m-%d') ,
    output_folder="Trials",
    process_portfolio=process_portfolio
)

import plotly.express as px

# ✅ Group by Date and calculate total portfolio value
portfolio_summary = (
    final_df.groupby("Date", as_index=False)["Buy_Hold_Value"].sum()
)

# ✅ Plot with Plotly
fig = px.line(
    portfolio_summary,
    x="Date",
    y="Buy_Hold_Value",
    title="Buy_Hold_Value Over Time",
    labels={"Date": "Date", "Buy_Hold_Value": "Buy_Hold_Value"},
    markers=True
)

fig.update_traces(line=dict(width=2))
fig.update_layout(width=1000,   # 🔑 width
                  height=500)    # 🔑 height

fig.show()

gc.collect()

final_df

gc.collect()

final_df

gc.collect()

old_df = final_df[~((final_df['Date']>'2025-11-30') & (final_df['Ticker']=='GOLDBEES'))]
old_df

gc.collect()

old_df['Ticker'].unique()

gc.collect()

# Build hedge book with month rebalancing (Dec/Jan -> Feb -> Mar) starting after 2025-11-30
portfolio_end_date = pd.to_datetime(final_df['Date']).max()

# Use the last GOLDBEES value before Dec as the hedge book starting capital
hedge_start_factor = final_df[(final_df['Ticker'] == 'GOLDBEES') & (final_df['Date'] <= '2025-11-30')].copy()
# (Fallback if GOLDBEES leg doesn't exist for some reason)
if hedge_start_factor.empty:
    hedge_start_factor = 25.0
else:
    hedge_start_factor = hedge_start_factor.sort_values('Date')['Buy_Hold_Value'].iloc[-1]

# --- Dec 2025 to Jan 2026 hedge: GOLDBEES + SILVERBEES + MOGSEC (60/20/20 of hedge book) ---
df_decjan = fetch_truedata_history(
    ticker_list=['GOLDBEES', 'SILVERBEES', 'MOGSEC'],
    duration='5 Y',
    bar_size='EOD',
    sleep_time=0.1
)[0]
df_decjan = df_decjan[["Date", "Ticker", "Open", "Close"]].copy()
df_decjan = df_decjan[(df_decjan['Date'] >= '2025-12-01') & (df_decjan['Date'] <= '2026-01-31')].copy()
df_decjan['%change'] = df_decjan.groupby('Ticker')['Close'].pct_change()

ticker_weights_decjan = {'GOLDBEES': 0.60, 'SILVERBEES': 0.20, 'MOGSEC': 0.20}
ticker_value_decjan = {t: w * hedge_start_factor for t, w in ticker_weights_decjan.items()}
df_decjan['BaseValue'] = df_decjan['Ticker'].map(ticker_value_decjan)
df_decjan['%change'] = pd.to_numeric(df_decjan['%change'])
df_decjan = df_decjan.sort_values(['Ticker', 'Date'])
df_decjan['ret_factor'] = 1 + df_decjan['%change'].fillna(0)
df_decjan['cum_factor'] = df_decjan.groupby('Ticker')['ret_factor'].cumprod()
df_decjan['Value_On_Date'] = df_decjan['BaseValue'] * df_decjan['cum_factor']
df_decjan = df_decjan[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})

# --- Feb 2026 hedge rebalance: sell SILVERBEES, rebalance hedge book to 40% GOLDBEES / 60% MOGSEC ---
feb_start = pd.Timestamp('2026-02-01')
feb_end = pd.Timestamp('2026-02-28')
df_feb = pd.DataFrame()
if portfolio_end_date >= feb_start:
    feb_factor = df_decjan.groupby('Date', as_index=False)['Buy_Hold_Value'].sum().sort_values('Date')['Buy_Hold_Value'].iloc[-1]
    df_feb = fetch_truedata_history(
        ticker_list=['GOLDBEES', 'MOGSEC'],
        duration='5 Y',
        bar_size='EOD',
        sleep_time=0.1
    )[0]
    df_feb = df_feb[["Date", "Ticker", "Open", "Close"]].copy()
    df_feb = df_feb[(df_feb['Date'] >= feb_start) & (df_feb['Date'] <= min(feb_end, portfolio_end_date))].copy()
    df_feb['%change'] = df_feb.groupby('Ticker')['Close'].pct_change()

    ticker_weights_feb = {'GOLDBEES': 0.40, 'MOGSEC': 0.60}
    ticker_value_feb = {t: w * feb_factor for t, w in ticker_weights_feb.items()}
    df_feb['BaseValue'] = df_feb['Ticker'].map(ticker_value_feb)
    df_feb['%change'] = pd.to_numeric(df_feb['%change'])
    df_feb = df_feb.sort_values(['Ticker', 'Date'])
    df_feb['ret_factor'] = 1 + df_feb['%change'].fillna(0)
    df_feb['cum_factor'] = df_feb.groupby('Ticker')['ret_factor'].cumprod()
    df_feb['Value_On_Date'] = df_feb['BaseValue'] * df_feb['cum_factor']
    df_feb = df_feb[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})

# --- Mar 2026 hedge rebalance: transfer MOGSEC holding to LIQUIDCASE ---
mar_start = pd.Timestamp('2026-03-01')
df_mar = pd.DataFrame()
if portfolio_end_date >= mar_start and not df_feb.empty:
    feb_last_date = df_feb['Date'].max()
    feb_last = df_feb[df_feb['Date'] == feb_last_date].set_index('Ticker')['Buy_Hold_Value'].to_dict()
    gold_base_mar = feb_last.get('GOLDBEES', 0.0)
    liquid_base_mar = feb_last.get('MOGSEC', 0.0)

    df_mar = fetch_truedata_history(
        ticker_list=['GOLDBEES', 'LIQUIDCASE'],
        duration='5 Y',
        bar_size='EOD',
        sleep_time=0.1
    )[0]
    df_mar = df_mar[["Date", "Ticker", "Open", "Close"]].copy()
    df_mar = df_mar[(df_mar['Date'] >= mar_start) & (df_mar['Date'] <= portfolio_end_date)].copy()
    df_mar['%change'] = df_mar.groupby('Ticker')['Close'].pct_change()

    ticker_value_mar = {'GOLDBEES': gold_base_mar, 'LIQUIDCASE': liquid_base_mar}
    df_mar['BaseValue'] = df_mar['Ticker'].map(ticker_value_mar)
    df_mar['%change'] = pd.to_numeric(df_mar['%change'])
    df_mar = df_mar.sort_values(['Ticker', 'Date'])
    df_mar['ret_factor'] = 1 + df_mar['%change'].fillna(0)
    df_mar['cum_factor'] = df_mar.groupby('Ticker')['ret_factor'].cumprod()
    df_mar['Value_On_Date'] = df_mar['BaseValue'] * df_mar['cum_factor']
    df_mar = df_mar[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})

df = pd.concat([df_decjan, df_feb, df_mar], ignore_index=True).sort_values(['Date', 'Ticker'])
df

gc.collect()



gc.collect()

# Hedge rebalancing is computed in the previous cell; quick sanity view:
df[['Date', 'Ticker', 'Buy_Hold_Value']].head()

gc.collect()

# (No-op) Hedge valuation already computed above.
df.tail()

gc.collect()

# df

gc.collect()

df['Buy_Value'] = df.groupby('Ticker')['Buy_Hold_Value'].transform('first')
df['Buy_Price'] = df.groupby('Ticker')['Close'].transform('first')
df['Quantity'] = df['Buy_Value'] / df['Buy_Price']
df

gc.collect()

conc_df = pd.concat([old_df, df])
conc_df

gc.collect()



gc.collect()

import plotly.express as px

# ✅ Group by Date and calculate total portfolio value
portfolio_summary = (
    conc_df.groupby("Date", as_index=False)["Buy_Hold_Value"].sum()
)
# ✅ Plot with Plotly
fig = px.line(
    portfolio_summary,
    x="Date",
    y="Buy_Hold_Value",
    title="Buy_Hold_Value Over Time",
    labels={"Date": "Date", "Buy_Hold_Value": "Buy_Hold_Value"},
    markers=True
)

fig.update_traces(line=dict(width=2))
fig.update_layout(width=1000,   # 🔑 width
                  height=500)    # 🔑 height
fig.show()

gc.collect()

# Momentum/Automating Momentum True Data/Trials/Nifty_500_2025_Apr_20_stocks_results_GoldSilverDebt_buy&hold_returns.xlsx

gc.collect()

 # conc_df.to_excel('C://Users//Admin//Momentum//Automating Momentum True Data//Trials//Nifty_500_2025_Apr_20_stocks_results_GoldSilverDebt_buy&hold_returns.xlsx', index=False)

gc.collect()

conc_df

gc.collect()

conc_df['Asset Type'] = np.where(
    conc_df['Ticker'] == 'GOLDBEES', 'Gold',
    np.where(
        conc_df['Ticker'] == 'SILVERBEES', 'Silver',
        np.where(
            conc_df['Ticker'] == 'MOGSEC', 'Debt',
            'Equities'
        )
    )
)

conc_df

gc.collect()

# conc_df = conc_df[conc_df['Date']<='2026-01-06']
conc_df = conc_df[conc_df['Date'] <= pd.Timestamp.today().normalize()]
conc_df

gc.collect()

conc_df.to_excel('Momentum_Maxfolio.xlsx', index=False)

gc.collect()