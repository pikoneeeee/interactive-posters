# -*- coding: utf-8 -*-
"""
Синхронизация контента из основного проекта в Android assets.

Использование:
    python sync_content.py                # Синхронизировать всё
    python sync_content.py physics        # Только физику
    python sync_content.py --list         # Показать доступные предметы

Структура:
    Общие файлы (subjects.json, locales, fonts, libs) → app/src/main/assets/
    Плакаты каждого предмета → app/src/<subject>/assets/posters/<subject>/

При добавлении новых плакатов:
    1. Добавьте HTML-файлы в content/posters/<subject>/
    2. Обновите content/subjects.json (добавьте topic)
    3. Запустите: python sync_content.py <subject>
"""

import json
import os
import shutil
import sys

# Пути
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # interactive-posters/
CONTENT_DIR = os.path.join(PROJECT_ROOT, 'content')
ANDROID_APP = os.path.join(SCRIPT_DIR, 'app')
MAIN_ASSETS = os.path.join(ANDROID_APP, 'src', 'main', 'assets')

# Все предметы (id из subjects.json)
ALL_SUBJECTS = [
    'physics', 'mathematics', 'biology', 'chemistry',
    'geography', 'informatics', 'historykaz', 'worldhistory',
    'kazakhlang', 'russianlang', 'englishlang',
    'music', 'grafika'
]


def sync_common_assets():
    """Копирует общие файлы в main/assets/ (subjects.json, locales, fonts, libs)"""
    print("\n=== Синхронизация общих файлов ===")

    # subjects.json
    src = os.path.join(CONTENT_DIR, 'subjects.json')
    dst = os.path.join(MAIN_ASSETS, 'subjects.json')
    if os.path.exists(src):
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        print(f"  ✓ subjects.json")

    # locales/
    sync_folder(
        os.path.join(CONTENT_DIR, 'locales'),
        os.path.join(MAIN_ASSETS, 'locales')
    )

    # fonts/
    sync_folder(
        os.path.join(CONTENT_DIR, 'fonts'),
        os.path.join(MAIN_ASSETS, 'fonts')
    )

    # libs/ (Chart.js и т.д.)
    sync_folder(
        os.path.join(CONTENT_DIR, 'libs'),
        os.path.join(MAIN_ASSETS, 'libs')
    )

    # assets/ (карты, таблицы Менделеева и т.д.) — общие для всех сборок.
    # Предметные папки (content/assets/<subject>/) НЕ кладём в общий main —
    # они копируются только в свой flavor (см. sync_subject_posters),
    # чтобы, например, картинки музыки не попадали в APK других предметов.
    sync_common_subdir_except_subjects(
        os.path.join(CONTENT_DIR, 'assets'),
        os.path.join(MAIN_ASSETS, 'assets')
    )

    # shanyrak_icon.svg
    icon_src = os.path.join(CONTENT_DIR, 'shanyrak_icon.svg')
    if os.path.exists(icon_src):
        shutil.copy2(icon_src, os.path.join(MAIN_ASSETS, 'shanyrak_icon.svg'))
        print(f"  ✓ shanyrak_icon.svg")


def sync_subject_posters(subject_id):
    """Копирует плакаты одного предмета в его flavor-каталог"""
    src_dir = os.path.join(CONTENT_DIR, 'posters', subject_id)
    dst_dir = os.path.join(ANDROID_APP, 'src', subject_id, 'assets', 'posters', subject_id)

    if not os.path.exists(src_dir):
        print(f"  ✗ Папка не найдена: {src_dir}")
        return 0

    # Также кладём плакаты в allsubjects flavor
    dst_all = os.path.join(ANDROID_APP, 'src', 'allsubjects', 'assets', 'posters', subject_id)

    count = sync_folder(src_dir, dst_dir)
    sync_folder(src_dir, dst_all)

    # Предметные ресурсы (картинки и т.п.): content/assets/<id>/ →
    # только в свой flavor и в allsubjects (НЕ в общий main).
    subj_assets = os.path.join(CONTENT_DIR, 'assets', subject_id)
    if os.path.exists(subj_assets):
        sync_folder(
            subj_assets,
            os.path.join(ANDROID_APP, 'src', subject_id, 'assets', 'assets', subject_id)
        )
        sync_folder(
            subj_assets,
            os.path.join(ANDROID_APP, 'src', 'allsubjects', 'assets', 'assets', subject_id)
        )

    # Создаём subjects_<id>.json с единственным предметом для этого flavor
    create_single_subject_json(subject_id)

    return count


def create_single_subject_json(subject_id):
    """Создаёт отфильтрованный subjects.json для однопредметного flavor"""
    full_path = os.path.join(CONTENT_DIR, 'subjects.json')
    if not os.path.exists(full_path):
        return

    with open(full_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    subjects = data.get('subjects', [])
    filtered = [s for s in subjects if s['id'] == subject_id]

    if not filtered:
        print(f"  ⚠ Предмет {subject_id} не найден в subjects.json")
        return

    out_data = {'subjects': filtered}
    out_dir = os.path.join(ANDROID_APP, 'src', subject_id, 'assets')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'subjects.json')

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    print(f"  ✓ subjects.json для {subject_id} ({len(filtered[0].get('topics', []))} тем)")


def sync_common_subdir_except_subjects(src, dst):
    """Копирует содержимое src → dst, пропуская папки с именем предмета.

    Предметные папки (например content/assets/music/) синхронизируются
    отдельно в свой flavor, поэтому в общий main их класть не нужно.
    """
    if not os.path.exists(src):
        return 0

    if os.path.exists(dst):
        shutil.rmtree(dst)
    os.makedirs(dst, exist_ok=True)

    count = 0
    for name in sorted(os.listdir(src)):
        if name in ALL_SUBJECTS:
            continue  # предметные ресурсы → в свой flavor, не в общий main
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            shutil.copytree(s, d)
            count += sum(len(files) for _, _, files in os.walk(d))
        else:
            shutil.copy2(s, d)
            count += 1
    print(f"  ✓ assets/ ({count} общих файлов)")
    return count


def sync_folder(src, dst):
    """Синхронизирует папку src → dst (полная замена)"""
    if not os.path.exists(src):
        return 0

    if os.path.exists(dst):
        shutil.rmtree(dst)

    shutil.copytree(src, dst)
    count = sum(len(files) for _, _, files in os.walk(dst))
    folder_name = os.path.basename(src)
    print(f"  ✓ {folder_name}/ ({count} файлов)")
    return count


def list_subjects():
    """Показывает список предметов и количество плакатов"""
    print("\n📚 Доступные предметы:")
    print("-" * 50)

    total = 0
    for subj in ALL_SUBJECTS:
        poster_dir = os.path.join(CONTENT_DIR, 'posters', subj)
        if os.path.exists(poster_dir):
            count = len([f for f in os.listdir(poster_dir) if f.endswith('.html')])
            total += count
            print(f"  {subj:<16} {count:>4} плакатов")
        else:
            print(f"  {subj:<16}    — не найден")

    print("-" * 50)
    print(f"  {'ИТОГО':<16} {total:>4} плакатов")


def main():
    args = sys.argv[1:]

    if '--list' in args or '-l' in args:
        list_subjects()
        return

    if '--help' in args or '-h' in args:
        print(__doc__)
        return

    # Определяем какие предметы синхронизировать
    if not args:
        subjects = ALL_SUBJECTS
        print("🔄 Полная синхронизация всех предметов")
    else:
        subjects = []
        for a in args:
            if a in ALL_SUBJECTS:
                subjects.append(a)
            else:
                print(f"⚠ Неизвестный предмет: {a}")
                print(f"  Доступные: {', '.join(ALL_SUBJECTS)}")
                return

    # 1. Общие файлы (всегда)
    sync_common_assets()

    # 2. Плакаты
    print("\n=== Синхронизация плакатов ===")
    total = 0
    for subj in subjects:
        print(f"\n📁 {subj}:")
        count = sync_subject_posters(subj)
        total += count

    print(f"\n✅ Синхронизация завершена! Всего файлов: {total}")
    print(f"\nДля сборки APK запустите:")
    if len(subjects) == 1:
        s = subjects[0]
        flavor = s[0].upper() + s[1:]
        print(f"  gradlew assemble{flavor}Release")
    else:
        print(f"  gradlew assembleRelease  (все предметы)")
        print(f"  gradlew assemble<Subject>Release  (один предмет)")


if __name__ == '__main__':
    main()
