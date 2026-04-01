"""Find dark text colors in ch_6-ch_45 that are unreadable on dark backgrounds"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# Tailwind dark text classes that would be invisible on dark bg
DARK_TEXT_CLASSES = [
    'text-gray-800', 'text-gray-900', 'text-gray-700', 'text-gray-600',
    'text-black', 'text-slate-800', 'text-slate-900', 'text-slate-700',
    'text-zinc-800', 'text-zinc-900', 'text-neutral-800', 'text-neutral-900',
    'text-stone-800', 'text-stone-900',
    # Dark accent text colors
    'text-emerald-800', 'text-emerald-900', 'text-emerald-700',
    'text-green-800', 'text-green-900', 'text-green-700',
    'text-blue-800', 'text-blue-900', 'text-blue-700',
    'text-amber-800', 'text-amber-900', 'text-amber-700',
    'text-red-800', 'text-red-900', 'text-red-700',
    'text-purple-800', 'text-purple-900', 'text-purple-700',
    'text-pink-800', 'text-pink-900', 'text-pink-700',
    'text-indigo-800', 'text-indigo-900', 'text-indigo-700',
    'text-yellow-800', 'text-yellow-900', 'text-yellow-700',
    'text-orange-800', 'text-orange-900', 'text-orange-700',
    'text-cyan-800', 'text-cyan-900', 'text-cyan-700',
    'text-teal-800', 'text-teal-900', 'text-teal-700',
    'text-violet-800', 'text-violet-900', 'text-violet-700',
    'text-rose-800', 'text-rose-900', 'text-rose-700',
    'text-sky-800', 'text-sky-900', 'text-sky-700',
    'text-lime-800', 'text-lime-900', 'text-lime-700',
    'text-fuchsia-800', 'text-fuchsia-900', 'text-fuchsia-700',
]

for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    found = []
    for cls in DARK_TEXT_CLASSES:
        if cls in html:
            found.append(cls)
    
    # Also check for inline style color with dark hex values
    dark_inline = re.findall(r'style="[^"]*color:\s*#(?:[0-3][0-9a-fA-F]{5}|[4-6][0-9a-fA-F]{5})', html)
    
    if found or dark_inline:
        print(f"ch_{i}.html: classes={found}, inline={dark_inline}")
