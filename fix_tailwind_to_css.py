# -*- coding: utf-8 -*-
"""
Заменяет во всех HTML:
  <script src="...tailwind.min.js"></script>
на:
  <link rel="stylesheet" href="...tailwind.min.css">
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')

JS_RE = re.compile(
    r'<script\s+src=["\']([^"\']*tailwind\.min\.js)["\'][^>]*>\s*</script>',
    re.IGNORECASE
)


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'tailwind.min.js' not in content:
        return False

    def make_link_tag(m):
        js_src = m.group(1)
        css_href = js_src.replace('tailwind.min.js', 'tailwind.min.css')
        return f'<link rel="stylesheet" href="{css_href}">'

    new_content = JS_RE.sub(make_link_tag, content)

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    print("=" * 60)
    print("ЗАМЕНА tailwind.min.js → tailwind.min.css (CSS файл)")
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
