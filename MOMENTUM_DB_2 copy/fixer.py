import re
import sys
import ast

with open('Integrated_Momentum.py', 'r', encoding='utf-8') as f:
    code = f.read()

# 1. Fix the magic commands
code = re.sub(r'^!\{sys\.executable\}(.*)$', r'import os; os.system(f\'"{sys.executable}"\1\')', code, flags=re.MULTILINE)

# 2. Add imports
imports = "import gc\nimport multiprocessing\nimport os\n"

# 3. Parse and indent top-level execution
lines = code.split('\n')
new_lines = []
in_main = False
has_added_imports = False

for line in lines:
    if not has_added_imports and line.startswith('import '):
        new_lines.append(imports)
        has_added_imports = True
        
    # Heuristic to find top level statements
    # We will indent everything after the functions are defined, starting from the first major execution:
    if not in_main and line.startswith('master_file = run_momentum_strategy('):
        in_main = True
        new_lines.append('if __name__ == "__main__":')
        new_lines.append('    multiprocessing.freeze_support()')
        
    if in_main:
        if line.startswith('def ') or line.startswith('import ') or line.startswith('from '):
            # We found a new function definition or import after main started, this happens because of the concat
            # We must break out of main, define the function at top level, then resume main.
            # Actually, to make it simple, we just won't indent 'def', 'import', 'from'
            new_lines.append(line)
        else:
            # Indent
            new_lines.append('    ' + line if line.strip() else line)
    else:
        new_lines.append(line)

# Let's insert gc.collect() in strategic places
final_lines = []
for line in new_lines:
    final_lines.append(line)
    if 'final_df = pd.concat(df_list, ignore_index=True) if df_list else pd.DataFrame()' in line:
        final_lines.append('    gc.collect()')
    elif 'final_df = pd.concat(df_lis).reset_index(drop=True)' in line:
        final_lines.append('    gc.collect()')
    elif 'print(f"✅ Final output saved to: {output_file}")' in line:
        final_lines.append('    gc.collect()')
    elif 'fig.show()' in line:
        final_lines.append('    gc.collect()')
    elif 'conc_df.to_excel(' in line:
        final_lines.append('    gc.collect()')

with open('Integrated_Momentum.py', 'w', encoding='utf-8') as f:
    f.write('\n'.join(final_lines))
