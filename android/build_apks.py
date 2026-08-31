# -*- coding: utf-8 -*-
"""
Удобная сборка APK для интерактивных плакатов.

Использование:
    python build_apks.py physics           # Собрать APK для физики
    python build_apks.py physics math      # Несколько предметов
    python build_apks.py all               # Все 11 отдельных APK
    python build_apks.py allsubjects       # Один APK со всеми предметами
    python build_apks.py --list            # Показать доступные предметы
    python build_apks.py --debug physics   # Debug-сборка

Перед сборкой автоматически запускается sync_content.py.
Готовые APK копируются в папку dist/.
"""

import os
import platform
import shutil
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DIST_DIR = os.path.join(PROJECT_ROOT, 'builds', 'android')


def ensure_java_home():
    """Автоматически находит JDK из Android Studio если JAVA_HOME не задан."""
    if os.environ.get('JAVA_HOME'):
        return  # Уже установлен

    # Типичные места, где Android Studio ставит JBR (JetBrains Runtime)
    candidates = [
        # Полноценный JDK 17 (Adoptium/Temurin) — нужен для AGP (jlink/jmods)
        r'D:\temurin17\jdk-17.0.19+10',
        r'D:\jdk17\jdk-17.0.18+8',
        # JBR из Android Studio (запасной вариант)
        r'D:\apps\jbr',
        # Стандартные пути установки Android Studio
        os.path.join(os.environ.get('ProgramFiles', ''), 'Android', 'Android Studio', 'jbr'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Programs', 'Android', 'Android Studio', 'jbr'),
    ]

    # Ищем studio64.exe рядом с jbr на всех дисках
    for drive in ['C:', 'D:', 'E:']:
        for root_dir in [drive + '\\', drive + '\\Program Files\\', drive + '\\apps\\']:
            jbr = os.path.join(root_dir, 'jbr')
            if jbr not in candidates:
                candidates.append(jbr)

    for path in candidates:
        java_exe = os.path.join(path, 'bin', 'java.exe')
        if os.path.isfile(java_exe):
            os.environ['JAVA_HOME'] = path
            print(f"☕ JAVA_HOME автоматически установлен: {path}")
            return

    print("⚠ JAVA_HOME не найден автоматически.")
    print("  Установите JDK 17 или Android Studio и пропишите JAVA_HOME.")


ensure_java_home()

ALL_SUBJECTS = [
    'physics', 'mathematics', 'biology', 'chemistry',
    'geography', 'informatics', 'historykaz', 'worldhistory',
    'kazakhlang', 'russianlang', 'englishlang',
    'music', 'grafika', 'labor_girls', 'nvp', 'labor_boys'
]

# Групповые сборки: один APK на несколько предметов (см. SUBJECT_GROUPS
# в sync_content.py). Собираются как обычный flavor, но в 'all' не входят —
# иначе история собиралась бы дважды.
GROUP_FLAVORS = ['history']

# Короткие алиасы для удобства
ALIASES = {
    'math': 'mathematics',
    'phys': 'physics',
    'bio': 'biology',
    'chem': 'chemistry',
    'geo': 'geography',
    'inf': 'informatics',
    'hist': 'historykaz',
    'whist': 'worldhistory',
    'kz': 'kazakhlang',
    'ru': 'russianlang',
    'en': 'englishlang',
    'mus': 'music',
    'gp': 'grafika',
    'graf': 'grafika',
    'nvp': 'nvp',
}


def get_gradlew():
    """Путь к gradlew"""
    if platform.system() == 'Windows':
        return os.path.join(SCRIPT_DIR, 'gradlew.bat')
    return os.path.join(SCRIPT_DIR, 'gradlew')


def flavor_name(subject_id):
    """Имя flavor с заглавной буквы для Gradle"""
    return subject_id[0].upper() + subject_id[1:]


def sync_content(subjects, legacy20=False):
    """Запускает sync_content.py"""
    print("\n📦 Синхронизация контента...")
    cmd = [sys.executable, os.path.join(SCRIPT_DIR, 'sync_content.py')] + subjects
    if legacy20:
        cmd.append('--legacy20')
    result = subprocess.run(cmd, cwd=SCRIPT_DIR)
    if result.returncode != 0:
        print("❌ Ошибка синхронизации контента!")
        sys.exit(1)


def build_apk(subject_id, debug=False, legacy20=False):
    """Собирает APK для одного предмета"""
    build_type = 'Debug' if debug else 'Release'
    task = f"assemble{flavor_name(subject_id)}{build_type}"

    print(f"\n🔨 Сборка: {subject_id} ({build_type})...")
    print(f"   Gradle task: {task}")

    gradlew = get_gradlew()
    if not os.path.exists(gradlew):
        print(f"❌ {gradlew} не найден!")
        print("   Откройте проект в Android Studio для генерации Gradle wrapper,")
        print("   или скачайте его: gradle wrapper --gradle-version 8.5")
        sys.exit(1)

    env = os.environ.copy()
    result = subprocess.run(
        [gradlew, task, '--stacktrace'],
        cwd=SCRIPT_DIR,
        env=env
    )

    if result.returncode != 0:
        print(f"❌ Ошибка сборки {subject_id}!")
        return False

    # Копируем APK в dist/
    bt = 'debug' if debug else 'release'
    apk_dir = os.path.join(
        SCRIPT_DIR, 'app', 'build', 'outputs', 'apk', subject_id, bt
    )

    # Ищем любой .apk в папке (имя может быть -unsigned, -debug и т.д.)
    apk_src = None
    if os.path.isdir(apk_dir):
        for f in os.listdir(apk_dir):
            if f.endswith('.apk'):
                apk_src = os.path.join(apk_dir, f)
                break

    if apk_src and os.path.exists(apk_src):
        os.makedirs(DIST_DIR, exist_ok=True)
        suffix = '-legacy20' if legacy20 else ''
        apk_dst = os.path.join(DIST_DIR, f'{subject_id}{suffix}-{bt}.apk')
        shutil.copy2(apk_src, apk_dst)
        size_mb = os.path.getsize(apk_dst) / (1024 * 1024)
        print(f"   ✅ {apk_dst} ({size_mb:.1f} MB)")
        return True
    else:
        print(f"   ⚠ APK не найден в: {apk_dir}")
        return False


def list_subjects():
    """Показывает доступные предметы"""
    print("\n📚 Доступные предметы для сборки:")
    print("-" * 50)
    for subj in ALL_SUBJECTS:
        aliases = [k for k, v in ALIASES.items() if v == subj]
        alias_str = f" (алиасы: {', '.join(aliases)})" if aliases else ""
        print(f"  {subj}{alias_str}")
    print("-" * 50)
    print("  allsubjects  — один APK со всеми предметами")
    print("  all          — собрать все 11 отдельных APK")


def main():
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print(__doc__)
        return

    if '--list' in args or '-l' in args:
        list_subjects()
        return

    # Парсим аргументы
    debug = '--debug' in args or '-d' in args
    legacy20 = '--legacy20' in args
    subjects_to_build = []

    for a in args:
        if a.startswith('-'):
            continue
        if a == 'all':
            subjects_to_build = ALL_SUBJECTS.copy()
            break
        # Разрешаем алиасы
        resolved = ALIASES.get(a, a)
        if resolved in ALL_SUBJECTS or resolved in GROUP_FLAVORS or resolved == 'allsubjects':
            subjects_to_build.append(resolved)
        else:
            print(f"⚠ Неизвестный предмет: {a}")
            print(f"  Запустите: python build_apks.py --list")
            return

    if not subjects_to_build:
        print("Не указаны предметы для сборки.")
        print("Запустите: python build_apks.py --help")
        return

    # Синхронизация контента
    sync_subjects = subjects_to_build if 'allsubjects' not in subjects_to_build else ALL_SUBJECTS
    sync_content(sync_subjects, legacy20=legacy20)

    # Сборка
    success = 0
    failed = 0
    for subj in subjects_to_build:
        if build_apk(subj, debug=debug, legacy20=legacy20):
            success += 1
        else:
            failed += 1

    # Итог
    print(f"\n{'=' * 50}")
    print(f"✅ Успешно: {success}  ❌ Ошибок: {failed}")
    if success > 0:
        print(f"📁 Готовые APK: {DIST_DIR}")
        print(f"   (EXE сборки: {os.path.join(PROJECT_ROOT, 'builds', 'windows')})")
    print(f"{'=' * 50}")


if __name__ == '__main__':
    main()
