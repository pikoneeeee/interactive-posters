# -*- coding: utf-8 -*-
"""
Заменяет во всех HTML:
  <link rel="stylesheet" href="...tailwind.min.css">
на:
  <script src="...tailwind.min.js"></script>

Play CDN JS (tailwind.min.js) уже скачан и работает оффлайн.
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')

CSS_RE = re.compile(
    r'<link\s+rel=["\']stylesheet["\']\s+href=["\']([^"\']*tailwind\.min\.css)["\'][^>]*/?>',
    re.IGNORECASE
)


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    if 'tailwind.min.css' not in content:
        return False

    def make_script_tag(m):
        css_href = m.group(1)
        js_src = css_href.replace('tailwind.min.css', 'tailwind.min.js')
        return f'<script src="{js_src}"></script>'

    new_content = CSS_RE.sub(make_script_tag, content)

    if new_content != content:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    return False


def main():
    print("=" * 60)
    print("🔧 ЗАМЕНА tailwind.min.css → tailwind.min.js")
    print("=" * 60)

    html_files = []
    for root, dirs, files in os.walk(CONTENT_DIR):
        for f in files:
            if f.endswith('.html'):
                html_files.append(os.path.join(root, f))

    print(f"\n📄 Найдено {len(html_files)} HTML файлов")

    modified = 0
    for i, path in enumerate(html_files):
        if fix_file(path):
            modified += 1
        if (i + 1) % 200 == 0:
            print(f"  Обработано {i + 1}/{len(html_files)}...")

    print(f"\n✅ Изменено {modified} из {len(html_files)} файлов")
    print("Теперь все плакаты используют tailwind.min.js (Play CDN оффлайн)")


if __name__ == '__main__':
    main()
