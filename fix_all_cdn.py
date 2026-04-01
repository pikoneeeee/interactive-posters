# -*- coding: utf-8 -*-
"""
Заменяет ВСЕ внешние CDN ссылки на локальные файлы:
- Google Fonts → fonts.css
- cdn.tailwindcss.com → tailwind.min.css
"""

import os
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')

# Паттерны для замены
PATTERNS = [
    # Google Fonts @import в <style>
    (
        re.compile(r"@import\s+url\(['\"]https://fonts\.googleapis\.com[^)]+\)[^;]*;?", re.IGNORECASE),
        ""
    ),
    # Google Fonts <link>
    (
        re.compile(r'<link[^>]*href=["\']https://fonts\.googleapis\.com[^"\']*["\'][^>]*/?>', re.IGNORECASE),
        lambda path: f'<link rel="stylesheet" href="{get_rel_path(path, "libs/fonts.css")}">'
    ),
    # Tailwind CDN script
    (
        re.compile(r'<script[^>]*src=["\']https://cdn\.tailwindcss\.com[^"\']*["\'][^>]*>\s*</script>', re.IGNORECASE),
        lambda path: f'<link rel="stylesheet" href="{get_rel_path(path, "libs/tailwind.min.css")}">'
    ),
]


def get_rel_path(html_path, target):
    """Вычисляет относительный путь от HTML файла до target в content/"""
    rel = os.path.relpath(os.path.join(CONTENT_DIR, target), os.path.dirname(html_path))
    return rel.replace('\\', '/')


def fix_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original = content
    
    for pattern, replacement in PATTERNS:
        if callable(replacement):
            content = pattern.sub(lambda m: replacement(path), content)
        else:
            content = pattern.sub(replacement, content)
    
    # Убираем дублирующиеся fonts.css ссылки
    fonts_link = f'<link rel="stylesheet" href="{get_rel_path(path, "libs/fonts.css")}">'
    count = content.count(fonts_link)
    if count > 1:
        # Оставляем только первое вхождение
        first_pos = content.find(fonts_link)
        content = content[:first_pos + len(fonts_link)] + content[first_pos + len(fonts_link):].replace(fonts_link, '')
    
    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    return False


def main():
    print("=" * 60)
    print("УДАЛЕНИЕ ВСЕХ ВНЕШНИХ CDN ЗАВИСИМОСТЕЙ")
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
