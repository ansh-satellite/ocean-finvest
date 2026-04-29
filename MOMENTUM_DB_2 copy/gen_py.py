import json
import os

with open('Integrated_Momentum.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

with open('Integrated_Momentum.py', 'w', encoding='utf-8') as f:
    f.write('import gc\nimport multiprocessing\nimport os\nimport sys\n\n')
    
    for cell in nb['cells']:
        if cell['cell_type'] == 'code':
            lines = []
            for line in cell['source']:
                if line.strip().startswith('!'):
                    cmd = line.strip()[1:]
                    lines.append(f'os.system(f"{cmd}")\n')
                else:
                    lines.append(line)
            f.write(''.join(lines) + '\n\n')
            f.write('gc.collect()\n\n')
