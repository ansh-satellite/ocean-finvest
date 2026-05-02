import re

with open('Integrated_Momentum.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Change sleep_time: float = 0.1 to 2.0
code = re.sub(r'sleep_time:\s*float\s*=\s*0\.1', 'sleep_time: float = 2.0', code)

lines = code.split('\n')
new_lines = []
for line in lines:
    if 'df = td_hist.get_historic_data([ticker], duration=duration, bar_size=bar_size)' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'for attempt in range(5):')
        new_lines.append(indent + '    try:')
        new_lines.append(indent + '        ' + line.lstrip())
        new_lines.append(indent + '        break')
        new_lines.append(indent + '    except Exception as api_e:')
        new_lines.append(indent + '        if attempt == 4: raise api_e')
        new_lines.append(indent + '        import time')
        new_lines.append(indent + '        time.sleep(2)')
    elif 'df_decjan = df_decjan[["Date", "Ticker", "Open", "Close"]].copy()' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if df_decjan.empty:')
        new_lines.append(indent + '    df_decjan = pd.DataFrame(columns=["Date", "Ticker", "Open", "Close", "Buy_Hold_Value"])')
        new_lines.append(indent + 'else:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_decjan['%change'] = df_decjan.groupby('Ticker')['Close'].pct_change()" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_decjan.empty:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_decjan['BaseValue'] = df_decjan['Ticker'].map(ticker_value_decjan)" in line or \
         "df_decjan['%change'] = pd.to_numeric(df_decjan['%change'])" in line or \
         "df_decjan = df_decjan.sort_values(['Ticker', 'Date'])" in line or \
         "df_decjan['ret_factor'] = 1 + df_decjan['%change'].fillna(0)" in line or \
         "df_decjan['cum_factor'] = df_decjan.groupby('Ticker')['ret_factor'].cumprod()" in line or \
         "df_decjan['Value_On_Date'] = df_decjan['BaseValue'] * df_decjan['cum_factor']" in line or \
         "df_decjan = df_decjan[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_decjan.empty:')
        new_lines.append(indent + '    ' + line.lstrip())

    elif 'df_feb = df_feb[["Date", "Ticker", "Open", "Close"]].copy()' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if df_feb.empty:')
        new_lines.append(indent + '    df_feb = pd.DataFrame(columns=["Date", "Ticker", "Open", "Close", "Buy_Hold_Value"])')
        new_lines.append(indent + 'else:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_feb['%change'] = df_feb.groupby('Ticker')['Close'].pct_change()" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_feb.empty:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_feb['BaseValue'] = df_feb['Ticker'].map(ticker_value_feb)" in line or \
         "df_feb['%change'] = pd.to_numeric(df_feb['%change'])" in line or \
         "df_feb = df_feb.sort_values(['Ticker', 'Date'])" in line or \
         "df_feb['ret_factor'] = 1 + df_feb['%change'].fillna(0)" in line or \
         "df_feb['cum_factor'] = df_feb.groupby('Ticker')['ret_factor'].cumprod()" in line or \
         "df_feb['Value_On_Date'] = df_feb['BaseValue'] * df_feb['cum_factor']" in line or \
         "df_feb = df_feb[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_feb.empty:')
        new_lines.append(indent + '    ' + line.lstrip())

    elif 'df_mar = df_mar[["Date", "Ticker", "Open", "Close"]].copy()' in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if df_mar.empty:')
        new_lines.append(indent + '    df_mar = pd.DataFrame(columns=["Date", "Ticker", "Open", "Close", "Buy_Hold_Value"])')
        new_lines.append(indent + 'else:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_mar['%change'] = df_mar.groupby('Ticker')['Close'].pct_change()" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_mar.empty:')
        new_lines.append(indent + '    ' + line.lstrip())
    elif "df_mar['BaseValue'] = df_mar['Ticker'].map(ticker_value_mar)" in line or \
         "df_mar['%change'] = pd.to_numeric(df_mar['%change'])" in line or \
         "df_mar = df_mar.sort_values(['Ticker', 'Date'])" in line or \
         "df_mar['ret_factor'] = 1 + df_mar['%change'].fillna(0)" in line or \
         "df_mar['cum_factor'] = df_mar.groupby('Ticker')['ret_factor'].cumprod()" in line or \
         "df_mar['Value_On_Date'] = df_mar['BaseValue'] * df_mar['cum_factor']" in line or \
         "df_mar = df_mar[['Date', 'Ticker', 'Open', 'Close', 'Value_On_Date', '%change']].rename(columns={'Value_On_Date': 'Buy_Hold_Value'})" in line:
        indent = line[:len(line) - len(line.lstrip())]
        new_lines.append(indent + 'if not df_mar.empty:')
        new_lines.append(indent + '    ' + line.lstrip())

    else:
        new_lines.append(line)

with open('Integrated_Momentum.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(new_lines))
