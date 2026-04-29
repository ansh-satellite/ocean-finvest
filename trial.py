# trailing_returns.py

from dummy import (
    load_and_process_data,
    build_daily_table,
    compute_portfolio_return_from_table,
    fetch_benchmark_return_truedata
)


# =========================================================
# FILE PATH
# =========================================================
DATA_PATH = r"C:\Users\LENOVO\Desktop\Ocean Finvest\MOMENTUM_DB_2 copy\Trials\Nifty_500_2025_apr_20_stocks_results_goldsilverdebt_buyhold_returns.xlsx"


# =========================================================
# FETCH DIRECTLY FROM DUMMY.PY LOGIC
# =========================================================
def get_daily_values_from_dummy():

    # Exact same raw data loading
    trades, last_update_date, raw_df, daily_snapshot = (
        load_and_process_data(DATA_PATH)
    )

    # Same active holdings logic
    active_holdings = trades[
        trades["Is_Active"]
    ].copy()

    # Same daily table logic
    daily_table = build_daily_table(
        active_holdings,
        daily_snapshot
    )

    # Same portfolio logic
    port_ret = compute_portfolio_return_from_table(
        daily_table
    )

    # Same benchmark logic
    bm = fetch_benchmark_return_truedata()

    benchmark_ret = bm["change_pct"]

    # Same alpha logic
    alpha = port_ret - benchmark_ret

    return {
        "Portfolio Change": round(port_ret, 2),
        "Benchmark Change": round(benchmark_ret, 2),
        "Alpha": round(alpha, 2)
    }


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":

    values = get_daily_values_from_dummy()

    print("\n===== DAILY VALUES FROM DUMMY.PY =====\n")

    print(
        "📈 Portfolio Change:",
        values["Portfolio Change"],
        "%"
    )

    print(
        "📊 BSE 500 Daily Change:",
        values["Benchmark Change"],
        "%"
    )

    print(
        "⚡ Alpha:",
        values["Alpha"],
        "%"
    )