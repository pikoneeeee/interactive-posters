"""Find all custom div/class names used in ch_6-ch_45 that need styling"""
import os, re, collections

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# Known styled classes - skip these
KNOWN = {
    'lang-content', 'lang-btn', 'active', 'lang-kk', 'lang-en', 'lang-ru',
    'rule-card', 'header-card', 'section-heading', 'glass', 'glass-accent',
    'rounded-custom', 'heading-font', 'formula-block', 'method-box',
    'property-box', 'substance-box', 'info-box', 'illustration',
    'overflow-x-auto', 'container',
}

box_classes = collections.Counter()

for i in range(6, 46):
    fp = os.path.join(POSTERS_DIR, f"ch_{i}.html")
    if not os.path.exists(fp):
        continue
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()
    
    for m in re.finditer(r'class="([^"]+)"', html):
        for cls in m.group(1).split():
            # Skip tailwind utility classes and known classes
            if cls in KNOWN:
                continue
            if re.match(r'^(text-|font-|flex|grid|md:|lg:|gap-|bg-|border-|oi-|is-|p-|m[btlrxy]?-|space-|uppercase|tracking-|rounded|items-|justify-|w-|h-|max-|min-|block|inline|hidden|relative|absolute|fixed|z-|top-|right-|left-|bottom-|col-|row-|self-)', cls):
                continue
            box_classes[cls] += 1

print("Custom classes found in ch_6-ch_45:")
for cls, cnt in box_classes.most_common(50):
    print(f"  .{cls}: {cnt} occurrences")
