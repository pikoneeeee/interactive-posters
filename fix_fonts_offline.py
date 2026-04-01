# -*- coding: utf-8 -*-
"""
Исправляет шрифты для оффлайн режима.
Скачивает Inter и Montserrat с поддержкой latin + cyrillic subset.
"""

import os
import re
import urllib.request
import ssl

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONTENT_DIR = os.path.join(BASE_DIR, 'content')
LIBS_DIR = os.path.join(CONTENT_DIR, 'libs')
FONTS_DIR = os.path.join(CONTENT_DIR, 'fonts')

# User-Agent Chrome чтобы Google Fonts вернул woff2
CHROME_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"


def make_ctx():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def fetch_text(url):
    req = urllib.request.Request(url, headers={'User-Agent': CHROME_UA})
    with urllib.request.urlopen(req, context=make_ctx()) as r:
        return r.read().decode('utf-8')


def fetch_bytes(url):
    req = urllib.request.Request(url, headers={'User-Agent': CHROME_UA})
    with urllib.request.urlopen(req, context=make_ctx()) as r:
        return r.read()


def download_fonts_from_google():
    """
    Берём оригинальный CSS от Google Fonts (с unicode-range),
    скачиваем все woff2 файлы и заменяем URL на локальные пути.
    """
    url = (
        "https://fonts.googleapis.com/css2"
        "?family=Inter:wght@300;400;600;700;800"
        "&family=Montserrat:wght@700;800;900"
        "&display=swap"
    )

    print(f"  📡 Запрашиваю CSS шрифтов от Google Fonts...")
    css = fetch_text(url)
    print(f"  ✅ Получено {len(css)} байт CSS")

    os.makedirs(FONTS_DIR, exist_ok=True)

    # Находим все woff2 URL в CSS
    woff2_pattern = re.compile(r'url\((https://fonts\.gstatic\.com/[^\)]+\.woff2)\)')
    url_to_filename = {}
    counter = [0]

    def replace_url(match):
        orig_url = match.group(1)
        if orig_url in url_to_filename:
            filename = url_to_filename[orig_url]
        else:
            counter[0] += 1
            filename = f"font_{counter[0]:04d}.woff2"
            url_to_filename[orig_url] = filename

            local_path = os.path.join(FONTS_DIR, filename)
            print(f"  📥 Скачиваю шрифт #{counter[0]}...")
            try:
                data = fetch_bytes(orig_url)
                with open(local_path, 'wb') as f:
                    f.write(data)
                print(f"     ✅ {filename} ({len(data):,} bytes)")
            except Exception as e:
                print(f"     ❌ Ошибка: {e}")
                return match.group(0)  # оставляем оригинальный URL

        return f"url('../fonts/{filename}')"

    updated_css = woff2_pattern.sub(replace_url, css)
    return updated_css


def write_fonts_css(css_content):
    path = os.path.join(LIBS_DIR, 'fonts.css')
    with open(path, 'w', encoding='utf-8') as f:
        f.write("/* Локальные шрифты Inter и Montserrat (latin + cyrillic) */\n\n")
        f.write(css_content)
    print(f"\n✅ Записан файл: {path}")


def main():
    print("=" * 60)
    print("🔤 ИСПРАВЛЕНИЕ ШРИФТОВ ДЛЯ ОФФЛАЙН РЕЖИМА")
    print("=" * 60)

    os.makedirs(LIBS_DIR, exist_ok=True)
    os.makedirs(FONTS_DIR, exist_ok=True)

    # Удаляем старые файлы шрифтов
    for f in os.listdir(FONTS_DIR):
        os.remove(os.path.join(FONTS_DIR, f))
        print(f"  🗑️  Удалён: {f}")

    print("\n📦 Скачиваем шрифты с кириллицей...")
    css = download_fonts_from_google()

    if not css.strip():
        print("❌ Не удалось скачать шрифты. Проверьте интернет-соединение.")
        return

    write_fonts_css(css)

    print("\n" + "=" * 60)
    print("✅ ШРИФТЫ ИСПРАВЛЕНЫ!")
    print("=" * 60)
    print(f"\nФайлы находятся в: content/fonts/")
    print(f"CSS файл: content/libs/fonts.css")


if __name__ == '__main__':
    main()
