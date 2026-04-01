"""Fix ALL remaining inline style hex backgrounds in ch_6-ch_45"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    original = html
    
    # Replace any inline style background with hex color -> dark glass
    # Pattern: style="...background: #hexcolor..." or "background-color: #hex..."
    # Replace the whole background value
    html = re.sub(
        r'(style="[^"]*?)background:\s*#[a-fA-F0-9]{3,6}([^;"]*)',
        r'\1background: rgba(255,255,255,0.05)\2',
        html
    )
    html = re.sub(
        r'(style="[^"]*?)background-color:\s*#[a-fA-F0-9]{3,6}([^;"]*)',
        r'\1background-color: rgba(255,255,255,0.05)\2',
        html
    )
    # Fix gradient backgrounds with hex colors
    html = re.sub(
        r'background:\s*linear-gradient\([^)]*#[a-fA-F0-9]{3,6}[^)]*\)',
        'background: rgba(255,255,255,0.05)',
        html
    )
    # Fix border colors with hex in inline styles
    html = re.sub(
        r'(style="[^"]*?)border-left:\s*\d+px\s+solid\s+#[a-fA-F0-9]{3,6}',
        r'\1border-left: 3px solid rgba(255,255,255,0.15)',
        html
    )
    html = re.sub(
        r'(style="[^"]*?)border-top:\s*\d+px\s+solid\s+#[a-fA-F0-9]{3,6}',
        r'\1border-top: 2px solid rgba(255,255,255,0.15)',
        html
    )
    
    if html != original:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"fixed ch_{i}.html")

print(f"\nFixed {count} files")
