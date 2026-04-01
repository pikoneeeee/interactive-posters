# -*- coding: utf-8 -*-
"""
Заменяет Chart.js CDN на локальный файл
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')

CHARTJS_PATTERN = re.compile(
    r'<script[^>]*src=["\']https://cdn\.jsdelivr\.net/npm/chart\.js[^"\']*["\'][^>]*>\s*</script>',
    re.IGNORECASE
)


def get_rel_path(html_path, target):
    rel = os.path.relpath(os.path.join(CONTENT_DIR, target), os.path.dirname(html_path))
    return rel.replace('\\', '/')


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    if 'cdn.jsdelivr.net/npm/chart.js' not in content:
        return False
    
    rel_path = get_rel_path(path, 'libs/chart.min.js')
    new_content = CHARTJS_PATTERN.sub(f'<script src="{rel_path}"></script>', content)
    
    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    print("=" * 60)
    print("ЗАМЕНА Chart.js CDN → локальный chart.min.js")
    print("=" * 60)

    html_files = []
    for root, dirs, files in os.walk(CONTENT_DIR):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))

    print(f"\nНайдено {len(html_files)} HTML файлов")

    modified = 0
    for i, path in enumerate(html_files):
        if fix_file(path):
            modified += 1
        if (i + 1) % 200 == 0:
            print(f"  Обработано {i + 1}/{len(html_files)}...")

    print(f"\nИзменено {modified} из {len(html_files)} файлов")


if __name__ == '__main__':
    main()
