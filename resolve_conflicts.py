import os
import re

def resolve_file(filepath, preference):
    if not os.path.exists(filepath): return
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # If no conflicts, return
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

# We want OURS for security fixes and remediations
resolve_file('backend/app/main.py', 'ours')
resolve_file('backend/app/api/dependencies.py', 'ours')
resolve_file('backend/app/worker.py', 'ours')
resolve_file('README.md', 'ours')
resolve_file('.gitignore', 'ours')
resolve_file('.env.example', 'theirs')

# We want THEIRS for new features
resolve_file('backend/app/api/routes/upload.py', 'theirs')
resolve_file('backend/app/services/claude_service.py', 'theirs')
resolve_file('backend/app/services/heuristic_params.py', 'theirs')

print("Conflicts resolved.")
