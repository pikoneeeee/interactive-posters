# -*- coding: utf-8 -*-
"""
Скрипт для конвертации всех HTML файлов на оффлайн режим.
Заменяет CDN ссылки Tailwind CSS и Google Fonts на локальные файлы.
"""

import os
import re
import urllib.request
import ssl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')
LIBS_DIR = os.path.join(CONTENT_DIR, 'libs')
FONTS_DIR = os.path.join(CONTENT_DIR, 'fonts')

# URLs для скачивания
TAILWIND_CDN_URL = "https://cdn.tailwindcss.com"
TAILWIND_LOCAL_FILE = "tailwind.min.js"

# Шрифты - скачаем основные веса
FONTS = {
    'Inter': {
        '300': 'https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2',
        '400': 'https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2',
        '600': 'https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2',
        '700': 'https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2',
        '800': 'https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2',
    },
    'Montserrat': {
        '700': 'https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXo.woff2',
        '800': 'https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXo.woff2',
        '900': 'https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXo.woff2',
    }
}


def download_file(url, dest_path):
    """Скачать файл по URL"""
    print(f"  📥 Скачиваю: {url}")
    try:
        # Игнорируем SSL ошибки для простоты
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, context=ctx) as response:
            data = response.read()
            with open(dest_path, 'wb') as f:
                f.write(data)
        print(f"  ✅ Сохранено: {dest_path} ({len(data)} bytes)")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка: {e}")
        return False


def ensure_dirs():
    """Создать необходимые директории"""
    os.makedirs(LIBS_DIR, exist_ok=True)
    os.makedirs(FONTS_DIR, exist_ok=True)
    print(f"📁 Директории готовы: {LIBS_DIR}, {FONTS_DIR}")


def download_tailwind():
    """Скачать Tailwind CSS CDN скрипт"""
    dest = os.path.join(LIBS_DIR, TAILWIND_LOCAL_FILE)
    if os.path.exists(dest):
        print(f"⏭️  Tailwind уже скачан: {dest}")
        return True
    return download_file(TAILWIND_CDN_URL, dest)


def download_fonts():
    """Скачать шрифты локально"""
    # Скачиваем Inter (variable font - один файл для всех весов)
    inter_url = "https://fonts.gstatic.com/s/inter/v13/UcCO3FwrK3iLTeHuS_fvQtMwCp50KnMw2boKoduKmMEVuLyfAZ9hiJ-Ek-_EeA.woff2"
    inter_dest = os.path.join(FONTS_DIR, "Inter-Variable.woff2")
    if not os.path.exists(inter_dest):
        download_file(inter_url, inter_dest)
    
    # Скачиваем Montserrat (variable font)
    montserrat_url = "https://fonts.gstatic.com/s/montserrat/v26/JTUHjIg1_i6t8kCHKm4532VJOt5-QNFgpCtr6Hw5aXo.woff2"
    montserrat_dest = os.path.join(FONTS_DIR, "Montserrat-Variable.woff2")
    if not os.path.exists(montserrat_dest):
        download_file(montserrat_url, montserrat_dest)


def create_fonts_css():
    """Создать CSS файл с локальными шрифтами"""
    css_content = """/* Локальные шрифты Inter и Montserrat */
@font-face {
    font-family: 'Inter';
    font-style: normal;
    font-weight: 300 800;
    font-display: swap;
    src: url('../fonts/Inter-Variable.woff2') format('woff2');
}

@font-face {
    font-family: 'Montserrat';
    font-style: normal;
    font-weight: 700 900;
    font-display: swap;
    src: url('../fonts/Montserrat-Variable.woff2') format('woff2');
}
"""
    css_path = os.path.join(LIBS_DIR, "fonts.css")
    with open(css_path, 'w', encoding='utf-8') as f:
        f.write(css_content)
    print(f"✅ Создан файл шрифтов: {css_path}")


def get_relative_path(html_path, target_path):
    """Вычислить относительный путь от HTML файла до целевого файла"""
    html_dir = os.path.dirname(html_path)
    rel_path = os.path.relpath(target_path, html_dir)
    return rel_path.replace('\\', '/')


def process_html_file(html_path):
    """Обработать один HTML файл"""
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Вычисляем относительные пути
        tailwind_rel = get_relative_path(html_path, os.path.join(LIBS_DIR, TAILWIND_LOCAL_FILE))
        fonts_css_rel = get_relative_path(html_path, os.path.join(LIBS_DIR, "fonts.css"))
        
        # 1. Заменяем Tailwind CDN на локальный
        content = re.sub(
            r'<script\s+src=["\']https://cdn\.tailwindcss\.com["\'][^>]*>\s*</script>',
            f'<script src="{tailwind_rel}"></script>',
            content
        )
        
        # 2. Заменяем Google Fonts на локальный CSS
        # Удаляем старую ссылку на Google Fonts
        content = re.sub(
            r'<link\s+href=["\']https://fonts\.googleapis\.com/css2\?[^"\']*["\'][^>]*>',
            f'<link rel="stylesheet" href="{fonts_css_rel}">',
            content
        )
        
        # Проверяем, были ли изменения
        if content != original_content:
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
        
    except Exception as e:
        print(f"  ❌ Ошибка при обработке {html_path}: {e}")
        return False


def process_all_html():
    """Обработать все HTML файлы"""
    html_files = []
    
    # Находим все HTML файлы
    for root, dirs, files in os.walk(CONTENT_DIR):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    print(f"\n📄 Найдено {len(html_files)} HTML файлов")
    
    modified = 0
    for i, html_path in enumerate(html_files):
        if process_html_file(html_path):
            modified += 1
        
        # Прогресс каждые 100 файлов
        if (i + 1) % 100 == 0:
            print(f"  Обработано {i + 1}/{len(html_files)}...")
    
    print(f"\n✅ Изменено {modified} из {len(html_files)} файлов")


def main():
    print("=" * 60)
    print("🔧 КОНВЕРТАЦИЯ НА ОФФЛАЙН РЕЖИМ")
    print("=" * 60)
    
    # 1. Создаем директории
    ensure_dirs()
    
    # 2. Скачиваем Tailwind
    print("\n📦 Скачиваем Tailwind CSS...")
    download_tailwind()
    
    # 3. Скачиваем шрифты
    print("\n🔤 Скачиваем шрифты...")
    download_fonts()
    
    # 4. Создаем CSS для шрифтов
    print("\n📝 Создаем CSS для шрифтов...")
    create_fonts_css()
    
    # 5. Обрабатываем все HTML файлы
    print("\n🔄 Обрабатываем HTML файлы...")
    process_all_html()
    
    print("\n" + "=" * 60)
    print("✅ КОНВЕРТАЦИЯ ЗАВЕРШЕНА!")
    print("=" * 60)
    print("\nТеперь приложение будет работать без интернета.")


if __name__ == "__main__":
    main()
