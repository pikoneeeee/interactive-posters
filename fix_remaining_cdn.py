# -*- coding: utf-8 -*-
"""
Исправляет ВСЕ оставшиеся CDN ссылки
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')


def get_rel_path(html_path, target):
    rel = os.path.relpath(os.path.join(CONTENT_DIR, target), os.path.dirname(html_path))
    return rel.replace('\\', '/')


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    # Font Awesome CDN
    content = re.sub(
        r'<link[^>]*href=["\']https://cdnjs\.cloudflare\.com/ajax/libs/font-awesome[^"\']*["\'][^>]*/?>',
        lambda m: f'<link rel="stylesheet" href="{get_rel_path(path, "libs/fontawesome.min.css")}">',
        content, flags=re.IGNORECASE
    )
    
    # Chart.js CDN (все варианты)
    content = re.sub(
        r'<script[^>]*src=["\']https://cdn\.jsdelivr\.net/npm/chart\.js[^"\']*["\'][^>]*>(\s*</script>)?',
        lambda m: f'<script src="{get_rel_path(path, "libs/chart.min.js")}"></script>',
        content, flags=re.IGNORECASE
    )
    
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    print("ИСПРАВЛЕНИЕ ОСТАВШИХСЯ CDN ССЫЛОК")
    
    html_files = []
    for root, dirs, files in os.walk(CONTENT_DIR):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))

    modified = 0
    for path in html_files:
        if fix_file(path):
            modified += 1

    print(f"Изменено {modified} файлов")


if __name__ == '__main__':
    main()
