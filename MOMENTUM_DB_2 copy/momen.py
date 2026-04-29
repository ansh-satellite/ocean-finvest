"""
Integrated Momentum Portfolio System
======================================
TWO SEPARATE PORTFOLIOS:

1. FULL HISTORY PORTFOLIO  (2023-04-01 to today)
   - Equity: top-N momentum stocks, 75 units allocation
   - Gold: GOLDBEES, 25 units allocation
   - After Nov-2025: GOLDBEES replaced by rebalanced hedge book
     (Dec/Jan: GOLDBEES 60% + SILVERBEES 20% + MOGSEC 20%)
     (Feb-2026: GOLDBEES 40% + MOGSEC 60%)
     (Mar-2026+: GOLDBEES + LIQUIDCASE)
   - Saved as: goldsilverdebt_buyhold_returns.xlsx

2. MOMENTUM MAXFOLIO  (2025-11-11 to today)  <-- SEPARATE PIPELINE
   - Same master momentum file, but data filtered from 2025-11-11 only
   - inception filter inside process_portfolio set to 2025-11-11
   - GOLDBEES rows before Dec-2025 kept; after Nov-2025 replaced by same
     hedge book logic seeded from that shorter run's GOLDBEES value
   - Saved as: Momentum_Maxfolio.xlsx

FIXES applied:
- KeyError/DateParseError: groupby().sum() returns Date-indexed Series;
  never re-index with ['col_name'] — use _last_total() helper everywhere.
- df_decjan forward-reference: initialised to empty DataFrame before use.
- All failed tickers written to failed_tickers_log.txt — code never stops.
"""

import gc
import os
import sys
import time
import logging
import warnings
import numpy as np
import pandas as pd
from datetime import date
from pathlib import Path
from dateutil.relativedelta import relativedelta

warnings.filterwarnings('ignore')

# =============================================================================
# LOGGING
# =============================================================================
LOG_FILE = "failed_tickers_log.txt"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("run_log.txt", mode='a', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


def log_failed_ticker(ticker: str, reason: str, log_file: str = LOG_FILE):
    ts = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a', encoding='utf-8') as fh:
        fh.write(f"[{ts}] FAILED | Ticker: {ticker:<20} | Reason: {reason}\n")


# =============================================================================
# SAFE HELPER — avoids KeyError / DateParseError on Date-indexed Series
# =============================================================================
def _last_total(df: pd.DataFrame, col: str = 'Buy_Hold_Value') -> float:
    """
    groupby('Date')[col].sum() returns a Series indexed by Date.
    Indexing that with ['col'] raises DateParseError -> KeyError.
    Use .iloc[-1] instead — always safe.
    """
    series = df.groupby('Date')[col].sum().sort_index()
    return float(series.iloc[-1]) if len(series) > 0 else 0.0


# =============================================================================
# TRUEDATA FETCH — ROBUST WITH RETRY + LOG
# =============================================================================
try:
    import streamlit as st
    TRUEDATA_USERNAME = st.secrets["TRUEDATA_USERNAME"]
    TRUEDATA_PASSWORD = st.secrets["TRUEDATA_PASSWORD"]
except Exception as e:
    logger.error(f"Failed to load credentials from st.secrets: {e}")
    TRUEDATA_USERNAME = ""
    TRUEDATA_PASSWORD = ""


def fetch_truedata_history(
    ticker_list: list,
    duration: str = '10 Y',
    bar_size: str = 'EOD',
    sleep_time: float = 0.15,
    max_retries: int = 3,
    log_file: str = LOG_FILE,
) -> tuple:
    """
    Returns (DataFrame[Date,Open,High,Low,Close,Ticker], list_of_failed_tickers).
    Never raises — failed tickers are logged and skipped.
    """
    from truedata import TD_hist

    with open(log_file, 'a', encoding='utf-8') as fh:
        fh.write(f"\n{'='*70}\n")
        fh.write(f"Session: {pd.Timestamp.now()}  Duration={duration}  BarSize={bar_size}\n")
        fh.write(f"{'='*70}\n")

    try:
        td = TD_hist(TRUEDATA_USERNAME, TRUEDATA_PASSWORD)
        logger.info("Connected to TrueData.")
    except Exception as e:
        logger.error(f"TrueData connection failed: {e}")
        for t in ticker_list:
            log_failed_ticker(t, f"Connection failed: {e}", log_file)
        empty = pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Ticker'])
        return empty, list(ticker_list)

    df_list, error_list = [], []

    for ticker in ticker_list:
        success, last_err = False, ""

        for attempt in range(1, max_retries + 1):
            try:
                raw = td.get_historic_data([ticker], duration=duration, bar_size=bar_size)

                if raw is None:
                    raise ValueError("API returned None")
                if isinstance(raw, pd.DataFrame) and raw.empty:
                    raise ValueError("API returned empty DataFrame")

                df = raw.copy()
                df.columns = [c.lower().strip() for c in df.columns]

                rename = {}
                for cand in ('timestamp', 'datetime', 'date', 'time'):
                    if cand in df.columns:
                        rename[cand] = 'Date'
                        break
                rename.update({'open': 'Open', 'high': 'High',
                               'low': 'Low', 'close': 'Close'})
                df = df.rename(columns=rename)

                missing = {'Date', 'Close'} - set(df.columns)
                if missing:
                    raise ValueError(f"Missing columns {missing}; got {list(df.columns)}")

                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
                df = df.dropna(subset=['Date'])
                df['Ticker'] = ticker

                for col in ('Open', 'High', 'Low'):
                    if col not in df.columns:
                        df[col] = np.nan

                df_list.append(df[['Date', 'Open', 'High', 'Low', 'Close', 'Ticker']])
                logger.info(f"  OK  {ticker:<22} {len(df)} rows  (attempt {attempt})")
                success = True
                break

            except Exception as exc:
                last_err = str(exc)
                logger.warning(f"  RETRY {ticker} attempt {attempt}/{max_retries}: {exc}")
                time.sleep(sleep_time * attempt)

        if not success:
            logger.error(f"  FAIL {ticker} after {max_retries} attempts -> {log_file}")
            log_failed_ticker(ticker, last_err, log_file)
            error_list.append(ticker)

        time.sleep(sleep_time)

    if df_list:
        out = pd.concat(df_list, ignore_index=True)
        out['Date'] = pd.to_datetime(out['Date'])
        out.sort_values(['Ticker', 'Date'], inplace=True)
        out.reset_index(drop=True, inplace=True)
    else:
        out = pd.DataFrame(columns=['Date', 'Open', 'High', 'Low', 'Close', 'Ticker'])

    logger.info(f"Fetch done: {len(ticker_list)-len(error_list)} OK | {len(error_list)} failed")
    return out, error_list


# =============================================================================
# MOMENTUM RANKING
# =============================================================================
def run_momentum_strategy(
    universe_file: str,
    start_date: str,
    end_date: str,
    top_n: int,
    output_root: str = "Momentum_Results",
) -> str:
    logger.info(f"Loading universe: {universe_file}")
    try:
        if universe_file.endswith(".csv"):
            stock_list = pd.read_csv(universe_file)[["Symbol", "ISIN Code"]]
        else:
            stock_list = pd.read_excel(universe_file)[["Symbol", "ISIN Code"]]
    except Exception as e:
        logger.error(f"Cannot load universe: {e}")
        return None

    stock_list["Ticker"] = stock_list["Symbol"]
    symbol_list = stock_list["Symbol"].tolist()
    universe_name = Path(universe_file).stem
    output_dir = os.path.join(output_root, f"{universe_name}_{top_n}_stocks_results")
    os.makedirs(output_dir, exist_ok=True)

    logger.info(f"Downloading prices for {len(symbol_list)} symbols...")
    data, _ = fetch_truedata_history(symbol_list, duration='10 Y', bar_size='EOD')
    if data.empty:
        logger.error("No price data — aborting.")
        return None

    data = data[['Date', 'Close', 'Ticker']].drop_duplicates(subset=['Date', 'Ticker'])
    prices_all = data.pivot(index='Date', columns='Ticker', values='Close').sort_index()
    logger.info(f"Price matrix: {prices_all.shape}")

    total_start = pd.to_datetime(start_date)
    total_end   = pd.to_datetime(end_date)
    windows, cur = [], total_start
    while True:
        nxt = cur + relativedelta(months=6)
        if nxt > total_end:
            break
        wp = prices_all.loc[(prices_all.index >= cur) & (prices_all.index < nxt)].copy()
        if not wp.empty:
            windows.append((cur, nxt, wp))
        cur += relativedelta(months=1)
    logger.info(f"Created {len(windows)} rolling windows.")

    for start, end, prices in windows:
        suffix = f"{start.strftime('%Y%m%d')}_{end.strftime('%Y%m%d')}"
        prices = prices.dropna(axis=1, how='all')
        if prices.empty:
            continue

        mc  = prices.groupby(prices.index.strftime('%Y-%m')).tail(1)
        ms  = prices.groupby(prices.index.strftime('%Y-%m')).head(1)
        ms.index = mc.index
        mom = (((mc - ms) / ms + 1).product() - 1) * 100

        dr      = prices.pct_change(fill_method=None)
        pos_pct = (dr[dr > 0].count() / dr.count()) * 100
        neg_pct = (dr[dr < 0].count() / dr.count()) * 100

        result = pd.concat([pos_pct, neg_pct, mom], axis=1, join='inner')
        result.columns = ["Positive", "Negative", "Momentum"]
        result = result.reset_index().rename(columns={'index': 'Ticker', 'Ticker': 'Ticker'})
        result = pd.merge(result, stock_list[["Ticker", "ISIN Code"]], on="Ticker", how="left")

        df = result.copy()
        df["Rank_Mom"] = df["Momentum"].rank(method='min', ascending=False)
        df['FIP'] = df.apply(
            lambda r: r['Negative'] - r['Positive'] if r['Momentum'] > 0 else np.nan, axis=1
        )
        df.dropna(inplace=True)
        if df.empty:
            continue

        df["FIP_rank"]      = df["FIP"].rank(method="first", ascending=True)
        df["Combined_Rank"] = df["Rank_Mom"] + df["FIP_rank"]

        if end.strftime('%Y-%m-%d') == '2026-01-01':
            df = df[~df['Ticker'].isin(['MARUTI', 'PTCIL'])]

        df = df.sort_values("Combined_Rank")
        last_close = prices.iloc[-1]
        df["CMP"] = df["Ticker"].map(last_close)
        before = len(df)
        df = df[df["CMP"] <= 7500].copy()
        if before - len(df):
            logger.info(f"  Removed {before-len(df)} stock(s) CMP > 7500")

        df = df.head(top_n).copy()
        df["Real_Rank"] = range(1, len(df) + 1)
        df["End_Date"]  = end.strftime('%Y-%m-%d')
        df.to_excel(os.path.join(output_dir, f"momentum_{suffix}.xlsx"), index=False)

    master_data = []
    for fn in os.listdir(output_dir):
        if fn.startswith("momentum_") and fn.endswith(".xlsx"):
            tmp = pd.read_excel(os.path.join(output_dir, fn))
            master_data.append(tmp[["End_Date", "ISIN Code", "Ticker", "Real_Rank"]])

    if not master_data:
        return None

    master_df   = pd.concat(master_data, ignore_index=True)
    master_path = os.path.join(output_dir, "master_momentum_summary.xlsx")
    master_df.to_excel(master_path, index=False)
    logger.info(f"Master file: {master_path}")
    return master_path


# =============================================================================
# PORTFOLIO PROCESSOR — supports inception_date filter
# =============================================================================
def process_portfolio(
    nav_df: pd.DataFrame,
    ticker_data: pd.DataFrame,
    initial_value: float = 75,
    inception_date=None,
    output_file: str = None,
) -> pd.DataFrame:
    """
    Month-by-month buy-and-hold rebalancing.

    inception_date : only price rows >= this date are used.
                     For full-history: "2023-04-01"
                     For Maxfolio:     "2025-11-11"  (matches original script)
    """
    if nav_df.empty or ticker_data.empty:
        logger.warning("process_portfolio: empty input.")
        return pd.DataFrame()

    df_lis = []
    last_val, last_qty = {}, {}

    nav_df = nav_df.sort_values(['Date', 'Ticker']).copy()
    nav_df['Date'] = pd.to_datetime(nav_df['Date'])
    ticker_data = ticker_data.sort_values(['Ticker', 'Date']).copy()
    ticker_data['Date'] = pd.to_datetime(ticker_data['Date'])

    inc_date = pd.to_datetime(inception_date) if inception_date else nav_df['Date'].min()

    for ym in nav_df['Year-Month'].drop_duplicates():
        month_nav = nav_df[nav_df['Year-Month'] == ym].copy()
        tickers   = month_nav['Ticker'].dropna().unique().tolist()
        sel_date  = pd.to_datetime(month_nav['Date'].min())
        ym_date   = pd.to_datetime(f"{ym}-01")

        prev_s = ym_date - relativedelta(months=2)
        cur_s  = ym_date
        cur_e  = ym_date + pd.offsets.MonthEnd(0)

        sd = ticker_data[
            (ticker_data['Date'] >= prev_s)
            & (ticker_data['Date'] <= cur_e)
            & (ticker_data['Ticker'].isin(tickers))
        ].copy()
        # KEY: apply inception filter — Maxfolio uses 2025-11-11
        sd = sd[sd['Date'] >= inc_date].copy()
        if sd.empty:
            continue

        sd['%change'] = sd.groupby('Ticker')['Close'].pct_change()
        flt = sd[(sd['Date'] >= cur_s) & (sd['Date'] <= cur_e)].copy()
        if flt.empty:
            continue

        if not last_val:
            alloc = {t: initial_value / max(len(tickers), 1) for t in tickers}
        else:
            alloc = {t: last_val[t] for t in tickers if t in last_val}
            dropped_val = sum(last_val[t] for t in last_val if t not in tickers)
            new_t = [t for t in tickers if t not in last_val]
            if new_t:
                per = dropped_val / len(new_t) if dropped_val else 0.0
                for t in new_t:
                    alloc[t] = per

        for ticker, iv in alloc.items():
            idx    = flt[flt['Ticker'] == ticker].index
            tkr_df = flt.loc[idx]
            if tkr_df.empty:
                continue

            flt.loc[idx, 'Initial_Allocation'] = iv
            flt.loc[idx, 'Selection_Date']     = sel_date
            flt.loc[idx, 'Buy_Hold_Value'] = iv * (
                (1 + flt.loc[idx, '%change'].fillna(0)).cumprod()
            )

            bp  = float(tkr_df.iloc[0]['Close'])
            qty = last_qty.get(ticker, (iv / bp) if bp else 0.0)
            flt.loc[idx, 'Buy_Price'] = bp
            flt.loc[idx, 'Quantity']  = qty

            if 'Real_Rank' in month_nav.columns:
                rr = month_nav.loc[month_nav['Ticker'] == ticker, 'Real_Rank']
                flt.loc[idx, 'Real_Rank'] = rr.iloc[0] if not rr.empty else np.nan

        last_qty = flt.groupby('Ticker')['Quantity'].last().to_dict()
        last_val = flt.groupby('Ticker')['Buy_Hold_Value'].last().to_dict()
        flt['Total_Portfolio_Value'] = flt.groupby('Date')['Buy_Hold_Value'].transform('sum')
        df_lis.append(flt)

    if not df_lis:
        logger.warning("process_portfolio: no output rows.")
        return pd.DataFrame()

    out = pd.concat(df_lis, ignore_index=True).sort_values(['Date', 'Ticker']).reset_index(drop=True)
    if output_file:
        out.to_excel(output_file, index=False)
    return out


# =============================================================================
# HEDGE BOOK BUILDER  (shared by both portfolios)
# =============================================================================
def _build_segment(
    hedge_prices: pd.DataFrame,
    start: pd.Timestamp,
    end: pd.Timestamp,
    base_values: dict,
    name: str,
) -> pd.DataFrame:
    seg = hedge_prices[
        (hedge_prices['Date'] >= start)
        & (hedge_prices['Date'] <= end)
        & (hedge_prices['Ticker'].isin(base_values))
    ][['Date', 'Ticker', 'Open', 'Close']].copy()

    if seg.empty:
        return seg

    seg = seg.sort_values(['Ticker', 'Date'])
    seg['%change']    = seg.groupby('Ticker')['Close'].pct_change()
    seg['ret_factor'] = 1 + seg['%change'].fillna(0)
    seg['cum_factor'] = seg.groupby('Ticker')['ret_factor'].cumprod()
    seg['Initial_Allocation'] = seg['Ticker'].map(base_values)
    seg['Buy_Hold_Value']     = seg['Initial_Allocation'] * seg['cum_factor']
    seg['Buy_Price']  = seg.groupby('Ticker')['Close'].transform('first')
    seg['Quantity']   = np.where(
        seg['Buy_Price'] > 0,
        seg['Initial_Allocation'] / seg['Buy_Price'],
        0.0
    )
    seg['Selection_Date']        = start
    seg['Hedge_Segment']         = name
    seg['Total_Portfolio_Value'] = seg.groupby('Date')['Buy_Hold_Value'].transform('sum')
    return seg.drop(columns=['ret_factor', 'cum_factor'])


def build_rebalanced_hedge_book(
    base_portfolio_df: pd.DataFrame,
    portfolio_end_date=None,
    default_hedge_value: float = 25.0,
) -> pd.DataFrame:
    """
    Three-leg hedge book starting Dec-2025.
    Seed value comes from the last GOLDBEES Buy_Hold_Value before 2025-11-30
    in whichever portfolio (full-history or Maxfolio) is passed in.
    """
    if base_portfolio_df.empty:
        return pd.DataFrame()

    cutoff = pd.Timestamp('2025-11-30')
    portfolio_end_date = (
        pd.to_datetime(portfolio_end_date)
        if portfolio_end_date is not None
        else pd.to_datetime(base_portfolio_df['Date']).max()
    )
    if portfolio_end_date <= cutoff:
        return pd.DataFrame()

    gold_rows  = base_portfolio_df[
        (base_portfolio_df['Ticker'] == 'GOLDBEES')
        & (base_portfolio_df['Date'] <= cutoff)
    ].sort_values('Date')
    hedge_seed = (
        float(gold_rows['Buy_Hold_Value'].iloc[-1])
        if not gold_rows.empty else default_hedge_value
    )
    logger.info(f"Hedge seed: {hedge_seed:.4f}")

    hedge_prices, _ = fetch_truedata_history(
        ['GOLDBEES', 'SILVERBEES', 'MOGSEC', 'LIQUIDCASE'],
        duration='5 Y', bar_size='EOD'
    )
    if hedge_prices.empty:
        logger.error("No hedge price data fetched.")
        return pd.DataFrame()

    segments  = []
    df_decjan = pd.DataFrame()
    df_feb    = pd.DataFrame()

    # Leg 1: Dec-2025 to Jan-2026
    decjan_s = pd.Timestamp('2025-12-01')
    decjan_e = min(pd.Timestamp('2026-01-31'), portfolio_end_date)
    if portfolio_end_date >= decjan_s:
        seg = _build_segment(
            hedge_prices, decjan_s, decjan_e,
            {'GOLDBEES':   0.60 * hedge_seed,
             'SILVERBEES': 0.20 * hedge_seed,
             'MOGSEC':     0.20 * hedge_seed},
            '2025-12_to_2026-01',
        )
        if not seg.empty:
            df_decjan = seg
            segments.append(df_decjan)

    # Leg 2: Feb-2026
    feb_s = pd.Timestamp('2026-02-01')
    feb_e = min(pd.Timestamp('2026-02-28'), portfolio_end_date)
    if portfolio_end_date >= feb_s and not df_decjan.empty:
        feb_seed = _last_total(df_decjan)          # FIX: never ['col'] on Date-Series
        if feb_seed == 0.0:
            feb_seed = hedge_seed
        seg = _build_segment(
            hedge_prices, feb_s, feb_e,
            {'GOLDBEES': 0.40 * feb_seed,
             'MOGSEC':   0.60 * feb_seed},
            '2026-02',
        )
        if not seg.empty:
            df_feb = seg
            segments.append(df_feb)

    # Leg 3: Mar-2026 onwards
    mar_s = pd.Timestamp('2026-03-01')
    if portfolio_end_date >= mar_s and not df_feb.empty:
        last_date = df_feb['Date'].max()
        last_vals = df_feb[df_feb['Date'] == last_date].set_index('Ticker')['Buy_Hold_Value']
        gold_val   = float(last_vals.get('GOLDBEES',  0.0))
        liquid_val = float(last_vals.get('MOGSEC',    0.0))
        seg = _build_segment(
            hedge_prices, mar_s, portfolio_end_date,
            {'GOLDBEES':   gold_val,
             'LIQUIDCASE': liquid_val},
            '2026-03_onward',
        )
        if not seg.empty:
            segments.append(seg)

    if not segments:
        logger.warning("Hedge book produced no segments.")
        return pd.DataFrame()

    return (
        pd.concat(segments, ignore_index=True)
        .sort_values(['Date', 'Ticker'])
        .reset_index(drop=True)
    )


# =============================================================================
# SHARED PIPELINE BUILDER
# =============================================================================
def build_portfolio_pipeline(
    master_file: str,
    filter_start: str,
    filter_end: str,
    inception_date: str,
    equity_allocation: float,
    gold_allocation: float,
    output_folder: str,
    output_label: str,
    ticker_data_equity: pd.DataFrame,   # pass pre-fetched data to avoid re-download
    ticker_data_gold: pd.DataFrame,
) -> pd.DataFrame:
    """
    Generic pipeline: load master -> filter dates -> process equity + gold ->
    strip post-Nov GOLDBEES -> attach hedge book -> label -> save.

    inception_date controls the price history cutoff inside process_portfolio.
    For full-history portfolio: "2023-04-01"
    For Maxfolio:               "2025-11-11"
    """
    nav_raw = pd.read_excel(master_file).rename(columns={'End_Date': 'Date'})
    nav_raw['Date'] = pd.to_datetime(nav_raw['Date'])

    sel_cols = ['Date', 'Ticker']
    if 'Real_Rank' in nav_raw.columns:
        sel_cols.append('Real_Rank')

    nav_df = (
        nav_raw[
            (nav_raw['Date'] >= filter_start) & (nav_raw['Date'] <= filter_end)
        ]
        .reset_index(drop=True)[sel_cols]
    )
    nav_df['Year-Month'] = nav_df['Date'].dt.to_period('M').astype(str)

    gold_nav = pd.DataFrame({
        'Date': nav_df['Date'].drop_duplicates().sort_values(),
        'Ticker': 'GOLDBEES',
    })
    if 'Real_Rank' in nav_df.columns:
        gold_nav['Real_Rank'] = np.nan
    gold_nav['Year-Month'] = pd.to_datetime(gold_nav['Date']).dt.to_period('M').astype(str)

    concat_df = (
        pd.concat([nav_df, gold_nav], ignore_index=True)
        .sort_values(['Date', 'Ticker'])
        .reset_index(drop=True)
    )

    eq_df  = concat_df.query("Ticker != 'GOLDBEES'")
    gld_df = concat_df.query("Ticker == 'GOLDBEES'")

    inc = pd.to_datetime(inception_date)

    final_eq  = process_portfolio(eq_df,  ticker_data_equity, equity_allocation, inception_date=inc)
    final_gld = process_portfolio(gld_df, ticker_data_gold,   gold_allocation,   inception_date=inc)

    final_df = (
        pd.concat([final_eq, final_gld], ignore_index=True)
        .sort_values(['Date', 'Ticker'])
        .reset_index(drop=True)
    )

    # Strip GOLDBEES after Nov-2025 (replaced by hedge book)
    old_df = final_df[
        ~((final_df['Date'] > '2025-11-30') & (final_df['Ticker'] == 'GOLDBEES'))
    ].copy()

    # Build hedge book seeded from this portfolio's GOLDBEES value
    portfolio_end = pd.to_datetime(final_df['Date']).max()
    hedge_df = build_rebalanced_hedge_book(
        base_portfolio_df  = final_df,
        portfolio_end_date = portfolio_end,
        default_hedge_value= gold_allocation,
    )

    # Combine
    frames = [old_df]
    if not hedge_df.empty:
        frames.append(hedge_df)
    conc_df = pd.concat(frames, ignore_index=True)
    conc_df = conc_df[conc_df['Date'] <= pd.Timestamp.today().normalize()]

    # Asset-type labels
    conds   = [
        conc_df['Ticker'] == 'GOLDBEES',
        conc_df['Ticker'] == 'SILVERBEES',
        conc_df['Ticker'].isin(['MOGSEC', 'LIQUIDCASE']),
    ]
    conc_df['Asset Type'] = np.select(conds, ['Gold', 'Silver', 'Debt'], default='Equities')

    conc_df = conc_df.sort_values(['Date', 'Ticker']).reset_index(drop=True)

    # Save
    os.makedirs(output_folder, exist_ok=True)
    out_path = os.path.join(output_folder, output_label)
    conc_df.to_excel(out_path, index=False)
    logger.info(f"Saved: {out_path}")

    return conc_df


# =============================================================================
# MAIN
# =============================================================================
if __name__ == "__main__":

    # Use relative paths for portability
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    UNIVERSE_FILE = os.path.join(SCRIPT_DIR, "Universe", "Nifty_500_2025_Apr.csv")
    MASTER_FILE   = os.path.join(SCRIPT_DIR, "Stocks", "Nifty_500_2025_Apr_20_stocks_results", "master_momentum_summary.xlsx")
    TODAY         = date.today().strftime('%Y-%m-%d')

    # ── A) Momentum Ranking (uncomment to regenerate) ──────────────────────
    # master_file = run_momentum_strategy(
    #     universe_file=UNIVERSE_FILE,
    #     start_date="2022-06-01",
    #     end_date="2026-04-01",
    #     top_n=20,
    #     output_root="Stocks",
    # )

    # ── B) Fetch price data ONCE — shared by both portfolios ───────────────
    logger.info("="*60 + "\nFetching shared price data\n" + "="*60)

    # Load ticker universe from master file to get full equity list
    nav_all = pd.read_excel(MASTER_FILE).rename(columns={'End_Date': 'Date'})
    all_equity_tickers = nav_all['Ticker'].dropna().unique().tolist()

    logger.info(f"Fetching equity data ({len(all_equity_tickers)} tickers)...")
    td_equity, _ = fetch_truedata_history(all_equity_tickers, duration='10 Y', bar_size='EOD')

    logger.info("Fetching GOLDBEES data...")
    td_gold, _ = fetch_truedata_history(['GOLDBEES'], duration='10 Y', bar_size='EOD')

    # ── C) PORTFOLIO 1 — Full History (2023-04-01 to today) ───────────────
    logger.info("="*60 + "\nPORTFOLIO 1: Full History (2023-04-01)\n" + "="*60)
    full_history_df = build_portfolio_pipeline(
        master_file       = MASTER_FILE,
        filter_start      = "2023-04-01",
        filter_end        = TODAY,
        inception_date    = "2023-04-01",   # price history starts here
        equity_allocation = 75,
        gold_allocation   = 25,
        output_folder     = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials",
        output_label      = "Nifty_500_2025_apr_20_stocks_goldsilverdebt_buyhold_returns.xlsx",
        ticker_data_equity= td_equity,
        ticker_data_gold  = td_gold,
    )
    logger.info(f"Portfolio 1 shape: {full_history_df.shape}")

    # ── D) PORTFOLIO 2 — Momentum MAXFOLIO (2025-11-11 to today) ──────────
    #
    # This is the SEPARATE portfolio from the original script.
    # Key differences vs Portfolio 1:
    #   - filter_start  = "2025-11-11"   (only momentum windows from this date)
    #   - inception_date= "2025-11-11"   (price history filtered from 2025-11-11
    #                                     inside process_portfolio — exactly as
    #                                     the original had the hardcoded line:
    #                                     stock_data[stock_data['Date']>='2025-11-11'])
    #   - equity/gold allocations same (75/25)
    #   - hedge book seeded independently from this portfolio's GOLDBEES value
    #
    logger.info("="*60 + "\nPORTFOLIO 2: Momentum MAXFOLIO (2025-11-11)\n" + "="*60)
    maxfolio_df = build_portfolio_pipeline(
        master_file       = MASTER_FILE,
        filter_start      = "2025-11-11",   # only windows from this date onwards
        filter_end        = TODAY,
        inception_date    = "2025-11-11",   # price history starts here (original hardcode)
        equity_allocation = 75,
        gold_allocation   = 25,
        output_folder     = os.path.join(SCRIPT_DIR, ".."),
        output_label      = "Momentum_Maxfolio.xlsx",
        ticker_data_equity= td_equity,
        ticker_data_gold  = td_gold,
    )
    logger.info(f"Portfolio 2 (Maxfolio) shape: {maxfolio_df.shape}")

    # ── E) BSE500 Benchmark ────────────────────────────────────────────────
    logger.info("Fetching BSE500 benchmark...")
    nse, _ = fetch_truedata_history(['BSE500'], duration='5 Y', bar_size='EOD')
    if not nse.empty:
        nse = nse[["Date", "Close"]].rename(columns={'Close': 'Buy_Hold_Value'})
        nse['%change'] = nse['Buy_Hold_Value'].pct_change()
        nse = nse[nse['Date'] >= '2023-04-01']
        os.makedirs("Trials", exist_ok=True)
        nse.to_excel('Trials/nse500_benchmark.xlsx', index=False)
        logger.info("Saved: Trials/nse500_benchmark.xlsx")

    # ── F) Plot both portfolios ────────────────────────────────────────────
    try:
        import plotly.express as px
        import plotly.graph_objects as go
        import plotly.io as pio

        pio.renderers.default = "browser"

        # Plot 1: Full History
        s1 = full_history_df.groupby("Date", as_index=False)["Buy_Hold_Value"].sum()
        fig1 = px.line(s1, x="Date", y="Buy_Hold_Value",
                       title="Portfolio 1 — Full History (2023-04-01)", markers=True)
        fig1.update_traces(line=dict(width=2))
        fig1.update_layout(width=1100, height=520)
        fig1.show()

        # Plot 2: Maxfolio
        s2 = maxfolio_df.groupby("Date", as_index=False)["Buy_Hold_Value"].sum()
        fig2 = px.line(s2, x="Date", y="Buy_Hold_Value",
                       title="Portfolio 2 — Momentum Maxfolio (2025-11-11)", markers=True)
        fig2.update_traces(line=dict(width=2, color='green'))
        fig2.update_layout(width=1100, height=520)
        fig2.show()

    except ImportError:
        logger.warning("plotly not installed — skipping charts.")

    gc.collect()
    logger.info("All done. Check 'failed_tickers_log.txt' for failed tickers.")
