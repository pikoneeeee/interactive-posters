#!/usr/bin/env python3
import os
import re
import glob

def fix_hardcoded_lang():
    """Исправляет жестко заданный язык в плакатах"""
    
    base_dir = "/Users/aydartleuzhanov/Desktop/InteractivePosters/content/posters"
    fixed_count = 0
    
    # Находим все HTML файлы
    html_files = []
    for root, dirs, files in os.walk(base_dir):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    print(f"🔍 Найдено {len(html_files)} HTML файлов")
    
    for file_path in html_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Ищем жестко заданный язык в window.onload
            original_content = content
            
            # Паттерны для поиска и замены
            patterns = [
                # window.onload = () => setLang('ru');
                (r'window\.onload\s*=\s*\(\)\s*=>\s*setLang\([\'\"](ru|kk|en)[\'\"]\);',
                 '''// Читаем язык из URL параметра
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'ru';
        console.log('Плакат: язык из URL =', lang);
        
        window.onload = () => setLang(lang);'''),
                
                # window.onload = function() { setLang('ru'); };
                (r'window\.onload\s*=\s*function\(\)\s*\{\s*setLang\([\'\"](ru|kk|en)[\'\"]\);\s*\};',
                 '''// Читаем язык из URL параметра
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'ru';
        console.log('Плакат: язык из URL =', lang);
        
        window.onload = function() { setLang(lang); };'''),
                
                # window.onload = setLang('ru');
                (r'window\.onload\s*=\s*setLang\([\'\"](ru|kk|en)[\'\"]\);',
                 '''// Читаем язык из URL параметра
        const urlParams = new URLSearchParams(window.location.search);
        const lang = urlParams.get('lang') || 'ru';
        console.log('Плакат: язык из URL =', lang);
        
        window.onload = () => setLang(lang);''')
            ]
            
            changed = False
            for pattern, replacement in patterns:
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    changed = True
                    print(f"   ✅ Исправлен: {os.path.basename(file_path)}")
                    break
            
            if changed:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_count += 1
            
        except Exception as e:
            print(f"   ❌ Ошибка в {file_path}: {e}")
    
    print(f"\n🎯 Исправлено {fixed_count} плакатов")

if __name__ == "__main__":
    fix_hardcoded_lang()
