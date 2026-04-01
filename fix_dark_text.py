"""Fix dark text colors that are unreadable on dark backgrounds in ch_6-ch_45"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# Dark text Tailwind classes -> light replacements
DARK_TO_LIGHT = {}
for color in ['gray','slate','zinc','neutral','stone','emerald','green','blue',
              'amber','red','purple','pink','indigo','yellow','orange','cyan',
              'teal','violet','rose','sky','lime','fuchsia']:
    for shade in ['700','800','900']:
        DARK_TO_LIGHT[f'text-{color}-{shade}'] = 'text-white/90'
DARK_TO_LIGHT['text-black'] = 'text-white/90'

count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    original = html
    
    # Replace dark Tailwind text classes
    for old, new in DARK_TO_LIGHT.items():
        if old in html:
            html = html.replace(old, new)
    
    # Replace inline dark color styles (like color: #059669)
    # These are mid-dark greens/blues that are hard to read on dark bg
    html = re.sub(
        r'style="color:\s*#[0-9a-fA-F]{6}"',
        'style="color: rgba(255,255,255,0.9)"',
        html
    )
    
    if html != original:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"fixed ch_{i}.html")

print(f"\nFixed {count} files")
