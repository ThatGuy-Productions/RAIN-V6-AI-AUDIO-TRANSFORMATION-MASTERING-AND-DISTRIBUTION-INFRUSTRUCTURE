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

# The feature/roon-crystal-ui branch is ahead in frontend design, so we prefer 'theirs'
resolve_file('frontend/src/components/layout/TopBar.tsx', 'theirs')
resolve_file('frontend/src/components/tabs/MasteringTab.tsx', 'theirs')
resolve_file('frontend/src/components/tabs/SpatialTab.tsx', 'theirs')
resolve_file('frontend/src/components/tabs/StemsTab.tsx', 'theirs')

print("Frontend conflicts resolved.")
