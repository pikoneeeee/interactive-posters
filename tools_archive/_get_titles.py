import re, os, glob
os.chdir(r'd:\Windsurf\в\плакаты\interactive-posters\content\posters\informatics2')
files = sorted(glob.glob('i2_*.html'), key=lambda x: int(x.split('_')[1].split('.')[0]))
for f in files:
    n = int(f.split('_')[1].split('.')[0])
    if not (144 <= n <= 158):
        continue
    c = open(f, encoding='utf-8').read()
    ru = re.search(r'<h1 lang="ru"[^>]*>([^<]+)</h1>', c)
    kk = re.search(r'<h1 lang="kk"[^>]*>([^<]+)</h1>', c)
    en = re.search(r'<h1 lang="en"[^>]*>([^<]+)</h1>', c)
    print(f"{f} | RU={ru.group(1) if ru else '?'} | KK={kk.group(1) if kk else '?'} | EN={en.group(1) if en else '?'}")
