import re

with open("improved_interface.py", "r", encoding="utf-8") as f:
    improved = f.read()

with open("Dash.py", "r", encoding="utf-8") as f:
    dash = f.read()

with open("nav_updater.py", "r", encoding="utf-8") as f:
    nav = f.read()

with open("trailing_returns.py", "r", encoding="utf-8") as f:
    trail = f.read()

# 1. Extract dash functions
dash_funcs = "\n# =========================\n# DASHBOARD INJECTED LOGIC\n# =========================\n"
dash_lines = dash.split('\n')
capturing = False
funcs_code = []
for line in dash_lines:
    if line.startswith("@st.cache_data") or line.startswith("def load_nav"):
        capturing = True
    if line.startswith("if __name__ =="):
        capturing = False
        
    if line.startswith("# =========================================================") and "PATCH for get_live_nav_data" in line:
        break
    
    if capturing:
        funcs_code.append(line)

# Handle the PATCH part manually
dash_patch = """
def get_live_nav_data():
    nav_df = load_nav()
    base_nav, base_date = get_base_nav(nav_df)
    data_df = load_dash_data()

    current_nav, return_pct, current_date, ref_date, current_sum, ref_sum = calculate_nav(
        data_df, base_nav
    )

    live_table = data_df[data_df["Date"] == current_date].copy()

    bm_return, bm_curr, bm_base, bm_curr_date, bm_base_date = calculate_benchmark()

    latest_file_row = nav_df.iloc[-1]
    if bm_curr is not None and bm_base is not None and bm_base != 0:
        current_bm_nav = latest_file_row["BM NAV"] * (bm_curr / bm_base)
    else:
        current_bm_nav = latest_file_row["BM NAV"] * (1 + (bm_return or 0) / 100)

    return {
        "nav_df":         nav_df,
        "live_table":     live_table,
        "current_nav":    current_nav,       
        "current_bm_nav": current_bm_nav,    
        "return":         return_pct,
        "bm_return":      bm_return,
    }
"""

dash_funcs += '\n'.join(funcs_code) + "\n" + dash_patch

dash_funcs = dash_funcs.replace("def load_data():", "def load_dash_data():")
dash_funcs = dash_funcs.replace("data_df = load_data()", "data_df = load_dash_data()")
dash_funcs = dash_funcs.replace("DATA_PATH", "DASH_DATA_PATH")

dash_globals = """
NAV_FILE_PATH  = r"C:\\Users\\LENOVO\\Desktop\\Ocean Finvest\\NAV.xlsx"
DASH_DATA_PATH = r"C:\\Users\\LENOVO\\Desktop\\Ocean Finvest\\MOMENTUM_DB_2 copy\\Momentum_Maxfolio.xlsx"
"""

# 2. Extract nav_updater functions
nav_funcs = "\n# =========================\n# NAV UPDATER INJECTED LOGIC\n# =========================\n"
nav_funcs += nav.replace("import pandas as pd\n", "")

# 3. Remove imports from improved
improved = improved.replace("from Dash import get_live_nav_data\n", "")
improved = improved.replace("from nav_updater import compute_calendar_returns\n", "")

# 4. Extract trail functions correctly
trail_funcs = "\n# =========================\n# TRAILING RETURNS INJECTED LOGIC\n# =========================\n"
capturing_trail = False
trail_code = []
for line in trail.split('\n'):
    if line.startswith("def get_1d_trailing_return"):
        capturing_trail = True
    
    if capturing_trail:
        trail_code.append(line)

trail_funcs += '\n'.join(trail_code) + "\n"

# Rename conflicting functions from trailing_returns
trail_funcs = trail_funcs.replace("def get_1d_trailing_return", "def tr_get_1d_trailing_return")
trail_funcs = trail_funcs.replace("def fetch_current_nav_values", "def tr_fetch_current_nav_values")
trail_funcs = trail_funcs.replace("def calculate_trailing_return", "def tr_calculate_trailing_return")
trail_funcs = trail_funcs.replace("def calculate_since_inception", "def tr_calculate_since_inception")
trail_funcs = trail_funcs.replace("fetch_current_nav_values(", "tr_fetch_current_nav_values(")
trail_funcs = trail_funcs.replace("calculate_trailing_return(", "tr_calculate_trailing_return(")
trail_funcs = trail_funcs.replace("calculate_since_inception(", "tr_calculate_since_inception(")

# 5. Fix the routing logic for show_trailing_returns
trail_replace_idx = improved.find("if st.session_state.show_trailing_returns:")
trail_replace_end = improved.find("st.title(\"🚀 Momentum Portfolio Dashboard\")")

routing_logic = """
if st.session_state.show_trailing_returns:
    show_trailing_returns_page()
    st.stop()
"""

improved = improved[:trail_replace_idx] + routing_logic + "\n# ═══════════════════════════════════════════════════════════\n# MAIN APP\n# ═══════════════════════════════════════════════════════════\n" + improved[trail_replace_end:]


# Combine
final_app = ""
imports_end = improved.find("TRUEDATA_USERNAME")
final_app += improved[:imports_end]
final_app += dash_globals + "\n"
final_app += dash_funcs + "\n"
final_app += nav_funcs + "\n"
final_app += trail_funcs + "\n"
final_app += improved[imports_end:]

# Fix duplicate "from truedata_ws.websocket.TD import TD" warning/error context
final_app = final_app.replace("import streamlit as st\n\nfrom Dash import get_live_nav_data", "import streamlit as st")

# Wait, `get_live_nav_data` in `Dash.py` needs `calculate_benchmark()` which requires `TD`.
# But `TD` is imported globally if we don't have it. `Dash.py` had it, we just make sure it's at the top.
if "from truedata_ws.websocket.TD import TD" not in final_app[:1000]:
    final_app = "from truedata_ws.websocket.TD import TD\n" + final_app

with open("app.py", "w", encoding="utf-8") as f:
    f.write(final_app)
