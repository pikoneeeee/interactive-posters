"""Batch fix: make all poster HTML files read language from localStorage on init.

Two poster types:
1. switchLang posters: use switchLang('kk'/'ru'/'en'), default class="lang-kk"
   Fix: insert a separate <script> tag right after the switchLang </script> that auto-inits
2. setLang posters: use setLang('ru'/'kz'/'en'), hardcoded in window.onload
   Fix: replace the last hardcoded setLang('ru') call with localStorage read
"""
import os
import glob

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters')

# Separate script tag for switchLang auto-init
SWITCH_LANG_INIT_TAG = """<script>/* poster-lang-init */
(function(){var s='ru';try{s=localStorage.getItem('poster_lang')||'ru'}catch(e){}
if(s==='kz')s='kk';if(typeof switchLang==='function')switchLang(s);})()
</script>"""

# For setLang posters: replacement for setLang('ru') in window.onload
SET_LANG_LS = "setLang((function(){try{return localStorage.getItem('poster_lang')||'ru'}catch(e){return 'ru'}})()"

stats = {'switchLang_fixed': 0, 'setLang_fixed': 0, 'skipped': 0, 'errors': 0}

for html_path in glob.glob(os.path.join(POSTERS_DIR, '**', '*.html'), recursive=True):
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()

        changed = False

        # --- Fix 1: switchLang posters ---
        # Insert auto-init script tag right after the </script> that contains switchLang
        if 'function switchLang(' in content and 'poster-lang-init' not in content:
            # Find the <script> block containing switchLang and its closing </script>
            idx_fn = content.find('function switchLang(')
            if idx_fn > -1:
                # Find the next </script> after the function
                idx_close = content.find('</script>', idx_fn)
                if idx_close > -1:
                    insert_pos = idx_close + len('</script>')
                    content = content[:insert_pos] + '\n' + SWITCH_LANG_INIT_TAG + content[insert_pos:]
                    changed = True
                    stats['switchLang_fixed'] += 1

        # --- Fix 2: setLang posters ---
        # Replace the LAST setLang('ru') or setLang('kz') call (in window.onload)
        if 'function setLang(' in content and 'poster-lang-init' not in content and not changed:
            for old_call in ["setLang('ru')", 'setLang("ru")', "setLang('kz')", 'setLang("kz")']:
                idx = content.rfind(old_call)
                if idx > -1:
                    # Make sure this isn't inside the function definition itself
                    fn_def_idx = content.find('function setLang(')
                    # The function body ends roughly within ~200 chars; the onload call is much later
                    if idx > fn_def_idx + 100:
                        content = content[:idx] + SET_LANG_LS + ')' + content[idx + len(old_call):]
                        changed = True
                        stats['setLang_fixed'] += 1
                        break

        if changed:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
        else:
            stats['skipped'] += 1

    except Exception as e:
        print(f"ERROR: {html_path}: {e}")
        stats['errors'] += 1

print(f"\n=== Results ===")
print(f"switchLang posters fixed: {stats['switchLang_fixed']}")
print(f"setLang posters fixed:    {stats['setLang_fixed']}")
print(f"Skipped (already ok):     {stats['skipped']}")
print(f"Errors:                   {stats['errors']}")
print(f"Total processed:          {sum(stats.values())}")
