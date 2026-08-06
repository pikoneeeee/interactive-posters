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

import oi_protocol   # сборочная криптография v4 (рядом со sync_content.py)

# Пути
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)  # interactive-posters/
CONTENT_DIR = os.path.join(PROJECT_ROOT, 'content')
ANDROID_APP = os.path.join(SCRIPT_DIR, 'app')
MAIN_ASSETS = os.path.join(ANDROID_APP, 'src', 'main', 'assets')

# Мусор, который НЕ должен попадать в APK (бэкапы, архивы, заметки разработчика).
# Применяется ко всем copytree — поэтому .bak/.zip/.rar/_STYLE_GUIDE.md и т.п.
# не синхронизируются в assets и не шифруются/не раздувают сборку.
_IGNORE_JUNK = shutil.ignore_patterns(
    '*.bak', '*.md', '*.zip', '*.rar', '*.7z', '*.orig', '*.tmp', '*.rej',
    '__pycache__', '*.pyc', 'Thumbs.db', '.DS_Store')

# Все предметы (id из subjects.json)
ALL_SUBJECTS = [
    'physics', 'mathematics', 'biology', 'chemistry',
    'geography', 'informatics', 'historykaz', 'worldhistory',
    'kazakhlang', 'russianlang', 'englishlang',
    'music', 'grafika', 'labor_girls', 'labor_boys', 'nvp'
]

# ── Новое ядро v4: защита контента + активация ──────────────────────────────
# Продукт «Интерактивные плакаты» в экосистеме.
PRODUCT_ID = 1

# Лицензируемые предметы → variant_id. ДОЛЖНО совпадать с VARIANT_ID во
# build.gradle.kts и со списком предметов в боте (/genqr). Бесплатные предметы
# (music, grafika, labor_*, nvp) сюда НЕ входят — их контент не шифруется.
# allsubjects = вариант 0 («все предметы»).
SUBJECT_VARIANTS = {
    'physics': 1, 'mathematics': 2, 'biology': 3, 'chemistry': 4,
    'geography': 5, 'informatics': 6, 'historykaz': 7, 'worldhistory': 8,
    'kazakhlang': 9, 'russianlang': 10, 'englishlang': 11,
}
VARIANT_ALL = 0   # ключ «все предметы» (сборка allsubjects)

# Мастер-ключ и публичный ключ экосистемы (заполняются load_keys() в main)
MASTER = None
PUB = None


def load_keys():
    """Находит ecosystem.keys и возвращает (content_master, ed25519_pub) в bytes.

    Приоритет: переменная OI_KEYS → android/ecosystem.keys → копия в репозитории
    экосистемы. Приватный ключ подписи НЕ используется (лицензии подписывает бот)."""
    candidates = [
        os.environ.get('OI_KEYS'),
        os.path.join(SCRIPT_DIR, 'ecosystem.keys'),
        r'D:\oi-orda-ecosystem\product-core\ecosystem.keys',
    ]
    for p in candidates:
        if p and os.path.exists(p):
            with open(p, 'r', encoding='utf-8') as f:
                ks = json.load(f)
            print(f"🔑 Ключи экосистемы: {p}")
            return bytes.fromhex(ks['content_master']), bytes.fromhex(ks['ed25519_pub'])
    print("❌ Не найден ecosystem.keys (мастер-ключ экосистемы).")
    print("   Без него нельзя зашифровать контент и встроить публичный ключ активации.")
    print("   Положите ecosystem.keys в папку android/ или задайте переменную OI_KEYS.")
    print(f"   Искал: {[c for c in candidates if c]}")
    sys.exit(1)


def write_product_config():
    """Кладёт product_config.json в main/assets: product_id + публичный ключ Ed25519."""
    cfg = {'product_id': PRODUCT_ID, 'public_key': list(PUB)}
    os.makedirs(MAIN_ASSETS, exist_ok=True)
    path = os.path.join(MAIN_ASSETS, 'product_config.json')
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False)
    print(f"  ✓ product_config.json (product_id={PRODUCT_ID}, публичный ключ Ed25519)")


def encrypt_dir(directory, content_key):
    """Шифрует ВСЕ файлы в directory на месте (OLENC2/AES-GCM). Идемпотентно:
    уже зашифрованные файлы пропускает. Возвращает число зашифрованных файлов."""
    if not os.path.isdir(directory):
        return 0
    n = 0
    for root, _dirs, files in os.walk(directory):
        for fn in files:
            fp = os.path.join(root, fn)
            with open(fp, 'rb') as f:
                raw = f.read()
            if oi_protocol.is_encrypted(raw):
                continue
            with open(fp, 'wb') as f:
                f.write(oi_protocol.encrypt_content(raw, content_key))
            n += 1
    return n


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

    # product_config.json — публичный ключ активации v4 (встраивается во все сборки)
    write_product_config()


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

    # ── Шифрование контента (новое ядро v4) ──────────────────────────
    # Свой flavor лицензируемого предмета — ключом этого предмета (variant).
    # Бесплатные предметы (нет в SUBJECT_VARIANTS) в своём flavor НЕ шифруются.
    if subject_id in SUBJECT_VARIANTS:
        ck = oi_protocol.derive_content_key(MASTER, PRODUCT_ID, SUBJECT_VARIANTS[subject_id])
        enc = encrypt_dir(dst_dir, ck)
        enc += encrypt_dir(os.path.join(ANDROID_APP, 'src', subject_id, 'assets', 'assets', subject_id), ck)
        print(f"  🔒 {subject_id}: зашифровано {enc} файлов (вариант {SUBJECT_VARIANTS[subject_id]})")
    # Копия в allsubjects всегда шифруется ключом «все предметы» (variant 0):
    # вся сборка allsubjects открывается одним ключом «все».
    ck_all = oi_protocol.derive_content_key(MASTER, PRODUCT_ID, VARIANT_ALL)
    enc_all = encrypt_dir(dst_all, ck_all)
    enc_all += encrypt_dir(os.path.join(ANDROID_APP, 'src', 'allsubjects', 'assets', 'assets', subject_id), ck_all)
    if enc_all:
        print(f"  🔒 allsubjects/{subject_id}: зашифровано {enc_all} файлов (вариант {VARIANT_ALL})")

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
            shutil.copytree(s, d, ignore=_IGNORE_JUNK)
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

    shutil.copytree(src, dst, ignore=_IGNORE_JUNK)
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

    # Ключи экосистемы (мастер контента + публичный ключ активации)
    global MASTER, PUB
    MASTER, PUB = load_keys()

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
