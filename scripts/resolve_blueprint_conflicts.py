import os

def resolve_file(filepath, preference):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if '<<<<<<<' not in content:
        return

    lines = content.split('\n')
    out_lines = []
    in_conflict = False
    keep_this_block = False

    for line in lines:
        if line.startswith('<<<<<<<'):
            in_conflict = True
            keep_this_block = (preference == 'ours')
            continue
        if line.startswith('======='):
            keep_this_block = (preference == 'theirs')
            continue
        if line.startswith('>>>>>>>'):
            in_conflict = False
            continue
        
        if not in_conflict:
            out_lines.append(line)
        elif keep_this_block:
            out_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines))

# We prefer 'ours' (which now contains release/consolidated and roon-crystal-ui)
# to avoid downgrading features
resolve_file('CLAUDE.md', 'ours')
resolve_file('backend/app/main.py', 'ours')
resolve_file('backend/app/services/billing.py', 'ours')
resolve_file('backend/app/services/heuristic_params.py', 'ours')
resolve_file('backend/app/services/identifiers.py', 'ours')
resolve_file('backend/app/services/master_engine.py', 'ours')
resolve_file('backend/app/tasks/analysis.py', 'ours')
resolve_file('frontend/src/types/dsp.ts', 'ours')
resolve_file('frontend/src/utils/heuristic-params.ts', 'ours')
resolve_file('rain-dsp/CMakeLists.txt', 'ours')

print("Blueprint conflicts resolved.")
