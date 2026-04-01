"""Fix table cell display in ch_6 - ch_45: table-cell instead of block"""
import os

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

TABLE_CELL_FIX = """
        /* Fix table cells: display table-cell instead of block */
        .lang-kk th.lang-content[lang="kk"],
        .lang-kk td.lang-content[lang="kk"],
        .lang-en th.lang-content[lang="en"],
        .lang-en td.lang-content[lang="en"],
        .lang-ru th.lang-content[lang="ru"],
        .lang-ru td.lang-content[lang="ru"] { display: table-cell; }"""

OLD_PATTERN = '.lang-kk .lang-content[lang="kk"], .lang-en .lang-content[lang="en"], .lang-ru .lang-content[lang="ru"] { display: block; }'

count = 0
for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        print(f"skip ch_{i}.html")
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    if "display: table-cell" in html:
        print(f"already fixed ch_{i}.html")
        continue
    if OLD_PATTERN in html:
        html = html.replace(OLD_PATTERN, OLD_PATTERN + TABLE_CELL_FIX)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
        print(f"fixed ch_{i}.html")
    else:
        print(f"pattern not found ch_{i}.html")

print(f"\nFixed {count} files")
