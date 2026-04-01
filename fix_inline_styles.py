"""Fix inline style attributes with old light-theme backgrounds in ch_6-ch_45.
Replaces light backgrounds with dark glass-themed ones."""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# Light background colors from old theme that need replacing
LIGHT_BG_COLORS = [
    '#fef3c7', '#dcfce7', '#f0fdf4', '#fde2e4', '#f0f9ff',
    '#bae6fd', '#fbcfe8', '#e0e7ff', '#dbeafe', '#ede9fe',
    '#fce7f3', '#ccfbf1', '#cffafe', '#fee2e2', '#fef9c3',
    '#fed7aa', '#d1fae5', '#fecaca', '#c7d2fe', '#a7f3d0',
    '#e5e7eb', '#f3f4f6', '#f9fafb', '#fff7ed', '#fefce8',
    '#f0fdfa', '#ecfdf5', '#eff6ff', '#eef2ff', '#faf5ff',
    '#fdf2f8', '#fff1f2', '#fefce8', '#fff7ed', '#f0fdfa',
]

# Solid accent colors used in borders/backgrounds
SOLID_COLORS_MAP = {
    '#d97706': 'rgba(255,255,255,0.2)',
    '#059669': 'rgba(255,255,255,0.2)',
    '#ca8a04': 'rgba(255,255,255,0.2)',
    '#be185d': 'rgba(255,255,255,0.2)',
    '#0284c7': 'rgba(255,255,255,0.2)',
    '#0369a1': 'rgba(255,255,255,0.2)',
    '#047857': 'rgba(255,255,255,0.2)',
    '#92400e': 'rgba(255,255,255,0.2)',
    '#9d174d': 'rgba(255,255,255,0.2)',
    '#7c3aed': 'rgba(255,255,255,0.2)',
    '#dc2626': 'rgba(255,255,255,0.2)',
    '#2563eb': 'rgba(255,255,255,0.2)',
    '#16a34a': 'rgba(255,255,255,0.2)',
    '#9333ea': 'rgba(255,255,255,0.2)',
    '#ea580c': 'rgba(255,255,255,0.2)',
    '#0891b2': 'rgba(255,255,255,0.2)',
}

def fix_inline_styles(html):
    changed = False
    
    # Replace light background colors in inline styles
    for color in LIGHT_BG_COLORS:
        if color in html:
            # In background property
            old = f'background: {color}'
            new = 'background: rgba(255,255,255,0.05)'
            if old in html:
                html = html.replace(old, new)
                changed = True
            # In background with gradient
            pattern = rf'background: linear-gradient\(135deg, {re.escape(color)} 0%, [^)]+\)'
            replacement = 'background: rgba(255,255,255,0.05)'
            html_new = re.sub(pattern, replacement, html)
            if html_new != html:
                html = html_new
                changed = True
    
    # Replace solid border colors in inline styles
    for old_color, new_color in SOLID_COLORS_MAP.items():
        # border-left with solid color
        old_border = f'border-left: 5px solid {old_color}'
        new_border = f'border-left: 3px solid {new_color}'
        if old_border in html:
            html = html.replace(old_border, new_border)
            changed = True
        old_border = f'border-left: 4px solid {old_color}'
        if old_border in html:
            html = html.replace(old_border, new_border)
            changed = True
        # border-top
        old_border = f'border-top: 4px solid {old_color}'
        new_border = f'border-top: 2px solid {new_color}'
        if old_border in html:
            html = html.replace(old_border, new_border)
            changed = True
        old_border = f'border-top: 5px solid {old_color}'
        if old_border in html:
            html = html.replace(old_border, new_border)
            changed = True
    
    # Replace background-color in inline styles
    for color in LIGHT_BG_COLORS:
        old = f'background-color: {color}'
        new = 'background-color: rgba(255,255,255,0.05)'
        if old in html:
            html = html.replace(old, new)
            changed = True
    
    return html, changed


count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    html_new, changed = fix_inline_styles(html)
    
    if changed:
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html_new)
        count += 1
        print(f"fixed ch_{i}.html")
    else:
        print(f"no inline styles to fix ch_{i}.html")

print(f"\nFixed {count} files")
