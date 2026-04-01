"""
Скрипт для обновления стиля плакатов ch_6 - ch_45 (химия)
из старого светлого стиля в новый тёмный glass morphism стиль.
"""
import os, re

POSTERS_DIR = os.path.join(os.path.dirname(__file__), 'content', 'posters', 'chemistry')

# Цветовые схемы для разнообразия (из новых плакатов)
COLOR_SCHEMES = [
    # (bg_gradient, accent_color, accent_light, accent_bg, border_color)
    ("radial-gradient(circle at top left, #0c1445, #1e1b4b, #0f172a)", "#818cf8", "#a5b4fc", "rgba(129,140,248,0.08)", "rgba(129,140,248,0.25)"),
    ("radial-gradient(circle at bottom left, #064e3b, #065f46, #0f172a)", "#34d399", "#6ee7b7", "rgba(52,211,153,0.08)", "rgba(52,211,153,0.25)"),
    ("radial-gradient(circle at top right, #451a03, #78350f, #1c1917)", "#f59e0b", "#fbbf24", "rgba(245,158,11,0.08)", "rgba(251,191,36,0.25)"),
    ("radial-gradient(circle at bottom right, #1e1b4b, #312e81, #0f172a)", "#a78bfa", "#c4b5fd", "rgba(167,139,250,0.08)", "rgba(167,139,250,0.25)"),
    ("radial-gradient(circle at top left, #052e16, #14532d, #0f172a)", "#4ade80", "#86efac", "rgba(74,222,128,0.08)", "rgba(74,222,128,0.25)"),
    ("radial-gradient(circle at bottom left, #172554, #1e3a5f, #0f172a)", "#38bdf8", "#7dd3fc", "rgba(56,189,248,0.08)", "rgba(56,189,248,0.25)"),
    ("radial-gradient(circle at top right, #4a044e, #581c87, #0f172a)", "#e879f9", "#f0abfc", "rgba(232,121,249,0.08)", "rgba(232,121,249,0.25)"),
    ("radial-gradient(circle at bottom right, #7c2d12, #9a3412, #1c1917)", "#fb923c", "#fdba74", "rgba(251,146,60,0.08)", "rgba(251,146,60,0.25)"),
]

def get_new_style(scheme_idx):
    bg, accent, accent_light, accent_bg, accent_border = COLOR_SCHEMES[scheme_idx % len(COLOR_SCHEMES)]
    return f"""
        body {{ font-family: 'Inter', sans-serif; background: {bg}; color: white; min-height: 100vh; }}
        .heading-font {{ font-family: 'Montserrat', sans-serif; }}
        .glass {{ background: rgba(10,15,35,0.70); border: 1px solid rgba(255,255,255,0.1); }}
        .glass-accent {{ background: {accent_bg}; border: 1px solid {accent_border}; }}
        .rounded-custom {{ border-radius: 2rem; }}
        .lang-btn {{ padding: 10px 24px; border-radius: 9999px; border: 1px solid rgba(255,255,255,0.2); background: transparent; color: white; font-weight: 700; cursor: pointer; font-size: 1.1rem; transition: all 0.2s; }}
        .lang-btn.active {{ background: {accent}; color: #0f172a; font-weight: 800; }}
        .lang-content {{ display: none; }}
        .lang-kk .lang-content[lang="kk"], .lang-en .lang-content[lang="en"], .lang-ru .lang-content[lang="ru"] {{ display: block; }}
        table {{ width: 100%; border-collapse: collapse; }}
        table th {{ background: rgba(255,255,255,0.08); color: {accent_light}; padding: 16px 20px; font-weight: 700; font-size: 1.05rem; text-align: left; border-bottom: 2px solid rgba(255,255,255,0.15); }}
        table td {{ padding: 14px 20px; border-bottom: 1px solid rgba(255,255,255,0.08); font-size: 1.05rem; vertical-align: top; color: rgba(255,255,255,0.85); }}
        table tr:hover td {{ background: rgba(255,255,255,0.03); }}
        .formula-block {{ background: rgba(0,0,0,0.5); color: {accent_light}; font-family: 'Courier New', monospace; padding: 18px 24px; border-radius: 1rem; font-size: 1.1rem; line-height: 1.7; white-space: pre; overflow-x: auto; border: 1px solid rgba(255,255,255,0.1); }}
        .section-heading {{ color: {accent_light}; font-family: 'Montserrat', sans-serif; font-size: 1.5rem; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 1.5rem; }}
        .rule-card {{ background: rgba(10,15,35,0.70); border: 1px solid rgba(255,255,255,0.1); border-radius: 2rem; padding: 2rem; margin-bottom: 1.5rem; }}
        .header-card {{ background: rgba(10,15,35,0.70); border: 1px solid rgba(255,255,255,0.1); border-radius: 2rem; padding: 2.5rem; }}
        .method-box, .property-box, .substance-box, .info-box, .illustration {{
            background: {accent_bg}; border: 1px solid {accent_border};
            border-radius: 1rem; padding: 1.25rem; margin: 0.75rem 0; border-left: none;
        }}
        svg text {{ fill: white !important; }}
        svg {{ max-width: 100%; height: auto; }}
    """

def transform_file(filepath, scheme_idx):
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Добавить fonts.css если нет
    if 'fonts.css' not in html:
        html = html.replace(
            '<link rel="stylesheet" href="../../libs/tailwind.min.css">',
            '<link rel="stylesheet" href="../../libs/tailwind.min.css">\n    <link rel="stylesheet" href="../../libs/fonts.css">'
        )

    # 2. Заменить <style> блок
    new_style = get_new_style(scheme_idx)
    html = re.sub(
        r'<style>.*?</style>',
        f'<style>{new_style}\n    </style>',
        html, count=1, flags=re.DOTALL
    )

    # 3. Заменить body class
    html = re.sub(
        r'<body class="[^"]*">',
        '<body class="p-6 md:p-10">',
        html
    )

    # 4. Заменить контейнер
    html = re.sub(
        r'<div id="poster-container" class="container lang-kk">',
        '<div id="poster-container" class="lang-kk" style="max-width:1500px;margin:auto;">',
        html
    )

    # 5. Обновить кнопки языка - из "Қазақша/English/Русский" в "KZ/EN/RU"
    html = re.sub(
        r'<div style="display:flex; justify-content:center; margin-bottom:20px; gap:10px;">\s*'
        r'<button class="lang-btn active" onclick="switchLang\(\'kk\'\)">Қазақша</button>\s*'
        r'<button class="lang-btn" onclick="switchLang\(\'en\'\)">English</button>\s*'
        r'<button class="lang-btn" onclick="switchLang\(\'ru\'\)">Русский</button>\s*'
        r'</div>',
        '',  # Убираем старые кнопки - добавим в header
        html
    )

    # 6. Обновить header: добавить кнопки языка внутрь
    accent = COLOR_SCHEMES[scheme_idx % len(COLOR_SCHEMES)][1]
    # Заменяем header-card text-center на glass rounded-custom с flex
    html = re.sub(
        r'<header class="header-card text-center mb-10">',
        '<header class="header-card rounded-custom mb-8 flex flex-col md:flex-row justify-between items-center">',
        html
    )
    
    # Добавляем кнопки языка перед закрытием header, оборачивая h1/p в div
    # Ищем </header> и добавляем кнопки перед ним
    if '<div class="flex gap-2' not in html:
        html = html.replace(
            '</header>',
            '        <div class="flex gap-2 mt-4 md:mt-0">\n'
            '            <button onclick="switchLang(\'ru\')" class="lang-btn active">RU</button>\n'
            '            <button onclick="switchLang(\'kk\')" class="lang-btn">KZ</button>\n'
            '            <button onclick="switchLang(\'en\')" class="lang-btn">EN</button>\n'
            '        </div>\n'
            '    </header>',
            1  # только первый header
        )

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return True

def main():
    count = 0
    for i in range(6, 46):
        filename = f"ch_{i}.html"
        filepath = os.path.join(POSTERS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"⚠️ {filename} не найден, пропускаю")
            continue
        
        scheme_idx = (i - 6) % len(COLOR_SCHEMES)
        try:
            transform_file(filepath, scheme_idx)
            print(f"✅ {filename} обновлён (схема {scheme_idx})")
            count += 1
        except Exception as e:
            print(f"❌ {filename}: {e}")
    
    print(f"\n{'='*50}")
    print(f"Обновлено {count} файлов")

if __name__ == '__main__':
    main()
