"""Find remaining inline style backgrounds in ch_6-ch_45 that look like light theme"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    for ln, line in enumerate(lines, 1):
        # Find inline style with background that has a hex color (light theme remnant)
        if 'style="' in line and 'background' in line:
            # Skip dark theme patterns
            if 'rgba(10,15,35' in line or 'rgba(255,255,255,0.0' in line:
                continue
            # Find hex colors in background
            matches = re.findall(r'background[^;"]*#[a-fA-F0-9]{3,6}', line)
            if matches:
                print(f"ch_{i}.html:{ln} -> {matches}")
