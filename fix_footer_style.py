"""Fix old light footer styles in ch_6 - ch_45"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    changed = False
    
    # Fix old light footer: background:#fed7aa etc -> dark glass style
    html_new = re.sub(
        r'<footer style="text-align: center; margin-top: 40px; padding: 24px; background: #[a-f0-9]+; border-radius: 1rem; border-top: 4px solid #[a-f0-9]+;">',
        '<footer style="text-align: center; margin-top: 40px; padding: 24px; background: rgba(10,15,35,0.70); border-radius: 2rem; border: 1px solid rgba(255,255,255,0.1);">',
        html
    )
    if html_new != html:
        changed = True
        html = html_new
    
    # Fix old footer text colors: text-amber-900 etc -> white
    html_new = re.sub(
        r'text-amber-900|text-emerald-900|text-blue-900|text-purple-900|text-green-900|text-pink-900|text-indigo-900|text-red-900|text-orange-900|text-cyan-900|text-violet-900|text-rose-900|text-teal-900|text-sky-900',
        'text-white',
        html
    )
    if html_new != html:
        changed = True
        html = html_new
    
    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"fixed ch_{i}.html")

print(f"\nFixed {count} files")
