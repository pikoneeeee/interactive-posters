#!/usr/bin/env python3
import os
import re

def update_all_posters():
    """Обновляет все плакаты чтобы они читали параметр языка из URL"""
    
    # Путь к плакатам
    posters_dir = '/Users/aydartleuzhanov/Desktop/InteractivePosters/content/posters'
    
    # Находим все HTML файлы плакатов
    html_files = []
    for root, dirs, files in os.walk(posters_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    print(f'Найдено {len(html_files)} плакатов')
    
    updated = 0
    for file_path in html_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем разные варианты инициализации языка
            patterns_to_fix = [
                # Вариант 1: window.onload = () => changeLang('ru');
                (r"window\.onload = \(\) => changeLang\('ru'\);", 
                 "window.onload = () => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get('lang') || 'ru'; // По умолчанию русский\n            console.log('🌐 Плакат загружен с языком:', lang);\n            changeLang(lang);\n        };"),

                # Вариант 2: window.onload = () => changeLang('kk');
                (r"window\.onload = \(\) => changeLang\('kk'\);", 
                 "window.onload = () => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get('lang') || 'kk'; // По умолчанию казахский\n            console.log('🌐 Плакат загружен с языком:', lang);\n            changeLang(lang);\n        };"),

                # Вариант 3: window.onload = () => changeLang('en');
                (r"window\.onload = \(\) => changeLang\('en'\);", 
                 "window.onload = () => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get('lang') || 'en'; // По умолчанию английский\n            console.log('🌐 Плакат загружен с языком:', lang);\n            changeLang(lang);\n        };"),

                # Вариант 4: switchLang('kk') в DOMContentLoaded
                (r"document\.addEventListener\('DOMContentLoaded', \(event\) => \{\s*switchLang\('kk'\);\s*\}\);", 
                 "document.addEventListener('DOMContentLoaded', (event) => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get('lang') || 'kk'; // По умолчанию казахский\n            console.log('🌐 Плакат загружен с языком:', lang);\n            switchLang(lang);\n        });")
            ]
            
            file_updated = False
            new_content = content
            
            for pattern, replacement in patterns_to_fix:
                if re.search(pattern, new_content, flags=re.MULTILINE | re.DOTALL):
                    new_content = re.sub(pattern, replacement, new_content, flags=re.MULTILINE | re.DOTALL)
                    file_updated = True
                    print(f'✅ Обновлен: {os.path.relpath(file_path, posters_dir)}')
                    break
            
            if file_updated:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated += 1
                
        except Exception as e:
            print(f'❌ Ошибка в {file_path}: {e}')
    
    print(f'\n🎯 Обновлено {updated} плакатов')

if __name__ == '__main__':
    update_all_posters()
