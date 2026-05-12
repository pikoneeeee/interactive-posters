#!/usr/bin/env python3
import os
import re

def remove_all_my_code(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Удаляем все <script> блоки с моим кодом
    content = re.sub(r'<script>.*?</script>', '', content, flags=re.DOTALL)
    
    # Удаляем комментарии
    content = re.sub(r'<!-- КНОПКА.*?-->', '', content, flags=re.DOTALL)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if not d.startswith('.')]
    for file in files:
        if file.endswith('.html') and 'templates' not in root and 'posters' in root:
            path = os.path.join(root, file)
            remove_all_my_code(path)
            print(f"Очищен: {path}")

print("Готово!")
