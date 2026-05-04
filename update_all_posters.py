#!/usr/bin/env python3
import os
import re

def update_all_remaining_posters():
    """Обновляет все оставшиеся плакаты чтобы они читали параметр языка из URL"""
    
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
            
            # Проверяем нужно ли обновлять этот плакат
            needs_update = False
            
            # Случай 1: Есть switchLang но нет инициализации
            if 'switchLang(' in content and 'URLSearchParams' not in content:
                needs_update = True
                
            # Случай 2: Есть changeLang но нет инициализации  
            if 'changeLang(' in content and 'URLSearchParams' not in content:
                needs_update = True
                
            # Случай 3: Есть window.onload с changeLang но не читает URL
            if 'window.onload' in content and 'changeLang(' in content and 'URLSearchParams' not in content:
                needs_update = True
            
            if not needs_update:
                continue
                
            # Обновляем плакат
            new_content = content
            
            # Ищем конец функции switchLang или changeLang
            patterns_to_add = [
                # Добавляем после switchLang функции
                (r'(function switchLang\(lang\) \{[^}]+\}\s*)', 
                 r'\1\n\n        // Инициализация языка из URL при загрузке\n        document.addEventListener(\'DOMContentLoaded\', (event) => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get(\'lang\') || \'kk\'; // По умолчанию казахский\n            console.log(\'🌐 Плакат загружен с языком:\', lang);\n            switchLang(lang);\n        });'),
                
                # Добавляем после changeLang функции
                (r'(function changeLang\(lang\) \{[^}]+\}\s*)', 
                 r'\1\n\n        // Инициализация языка из URL при загрузке\n        document.addEventListener(\'DOMContentLoaded\', (event) => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get(\'lang\') || \'kk\'; // По умолчанию казахский\n            console.log(\'🌐 Плакат загружен с языком:\', lang);\n            changeLang(lang);\n        });'),
                
                # Заменяем window.onload = () => changeLang('...');
                (r'window\.onload = \(\) => changeLang\([\'"]{1}[a-z]{2}[\'"]{1}\);', 
                 'window.onload = () => {\n            // Читаем параметр языка из URL\n            const urlParams = new URLSearchParams(window.location.search);\n            const lang = urlParams.get(\'lang\') || \'kk\'; // По умолчанию казахский\n            console.log(\'🌐 Плакат загружен с языком:\', lang);\n            changeLang(lang);\n        };')
            ]
            
            file_updated = False
            for pattern, replacement in patterns_to_add:
                if re.search(pattern, new_content, flags=re.MULTILINE | re.DOTALL):
                    new_content = re.sub(pattern, replacement, new_content, flags=re.MULTILINE | re.DOTALL)
                    file_updated = True
                    break
            
            if file_updated:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                updated += 1
                print(f'✅ Обновлен: {os.path.relpath(file_path, posters_dir)}')
                
        except Exception as e:
            print(f'❌ Ошибка в {file_path}: {e}')
    
    print(f'\n🎯 Обновлено {updated} плакатов')

if __name__ == '__main__':
    update_all_remaining_posters()
