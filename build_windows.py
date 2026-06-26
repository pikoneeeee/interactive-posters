# -*- coding: utf-8 -*-
"""
Универсальная сборка Windows-установщика с выбором предметов.

Использование:
    python build_windows.py physics           # EXE для физики
    python build_windows.py chem math         # Два отдельных EXE
    python build_windows.py all               # 11 отдельных EXE
    python build_windows.py allsubjects       # Один EXE со всеми предметами
    python build_windows.py --list            # Показать доступные предметы
    python build_windows.py --no-installer    # Только EXE-папка, без Inno Setup
    python build_windows.py --clean physics   # Очистить build/ перед сборкой
    python build_windows.py --skip-activation chem  # Без окна активации

Шаги для каждого предмета:
1. Staging — копирует только нужный контент.
2. Генерирует .ico из SVG.
3. PyInstaller --onedir --windowed.
4. Inno Setup (если установлен и не --no-installer).
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Принудительный UTF-8 на Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parent
BUILD_DIR = ROOT / "_build_temp"
BUILDS_DIR = ROOT / "builds" / "windows"
APP_VERSION = "1.1.0"
APP_PUBLISHER = "DigiTouch"

ALL_SUBJECTS = [
    "physics", "mathematics", "biology", "chemistry",
    "geography", "informatics", "historykaz", "worldhistory",
    "kazakhlang", "russianlang", "englishlang", "nvp",
]

# Короткие алиасы (такие же как в build_apks.py)
ALIASES = {
    "math": "mathematics",
    "phys": "physics",
    "bio": "biology",
    "chem": "chemistry",
    "geo": "geography",
    "inf": "informatics",
    "hist": "historykaz",
    "whist": "worldhistory",
    "kz": "kazakhlang",
    "ru": "russianlang",
    "en": "englishlang",
    "nvp": "nvp",
}

# Читаемые имена для заголовка окна и инсталлятора
DISPLAY_NAMES = {
    "physics":      "Физика",
    "mathematics":  "Математика",
    "biology":      "Биология",
    "chemistry":    "Химия",
    "geography":    "География",
    "informatics":  "Информатика",
    "historykaz":   "История Казахстана",
    "worldhistory": "Всемирная история",
    "kazakhlang":   "Қазақ тілі",
    "russianlang":  "Русский язык",
    "englishlang":  "Английский язык",
    "nvp":          "НВП",
}

# Приложение использует только: QtCore, QtGui, QtWidgets, QtNetwork,
# QtWebEngineCore, QtWebEngineWidgets, QtWebChannel.
# Всё остальное PySide6 — мёртвый груз (десятки DLL, сотни МБ).
PYSIDE6_EXCLUDES = [
    # Qt3D — мёртвый груз, ~50 МБ
    "PySide6.Qt3DAnimation", "PySide6.Qt3DCore", "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput", "PySide6.Qt3DLogic", "PySide6.Qt3DRender",
    # Беспроводные/сенсоры/железо
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSensors",
    "PySide6.QtSerialBus", "PySide6.QtSerialPort",
    # Графики/визуализация
    "PySide6.QtCharts", "PySide6.QtChartsQml",
    "PySide6.QtDataVisualization",
    "PySide6.QtGraphs", "PySide6.QtGraphsWidgets",
    # Дизайнер/help/тесты — только для разработки
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtTest",
    "PySide6.QtUiTools",
    # Сервер/протоколы — не нужны
    "PySide6.QtHttpServer", "PySide6.QtNetworkAuth",
    "PySide6.QtRemoteObjects", "PySide6.QtWebSockets",
    # Геолокация (Qt6Location — не путать с Qt6Positioning, который нужен WebEngine)
    "PySide6.QtLocation",
    # Мультимедиа/звук — большой груз
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtSpatialAudio", "PySide6.QtTextToSpeech",
    # PDF — не используем (Qt6Pdf отдельный от встроенного в Chromium)
    "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    # QML/Quick3D — 3D-движок не нужен.
    # ВНИМАНИЕ: базовые QtQml, QtQuick, QtQuickWidgets НЕЛЬЗЯ исключать —
    # Qt6WebEngineCore.dll зависит от Qt6Qml.dll/Qt6Quick.dll на уровне DLL!
    "PySide6.QtQuick3D",
    "PySide6.QtQuickControls2",
    # Прочее
    "PySide6.QtScxml", "PySide6.QtSql", "PySide6.QtStateMachine",
    "PySide6.QtSvgWidgets",  # сам QtSvg оставляем — нужен для icon.svg
    "PySide6.QtXml", "PySide6.QtDBus",
]


def log(msg: str) -> None:
    print(f"[build] {msg}")


# ────────────── helpers ──────────────

def app_name_for(subject_id: str) -> str:
    """InteractivePosters-Physics и т.д."""
    return f"InteractivePosters-{subject_id.capitalize()}"


def display_name_for(subject_id: str) -> str:
    name = DISPLAY_NAMES.get(subject_id, subject_id.capitalize())
    return f"Интерактивные плакаты — {name}"


# ────────────── Шаг 1. Staging ──────────────

def prepare_staging(subjects: list[str], *, start_subject: str | None,
                    skip_activation: bool, display_title: str) -> Path:
    """Готовит _build_staging/content/ с нужными предметами."""
    staging = ROOT / "_build_staging"
    staging_content = staging / "content"
    if staging_content.exists():
        shutil.rmtree(staging_content)
    staging_content.mkdir(parents=True)

    src_content = ROOT / "content"

    # Общие папки
    for folder in ("locales", "templates", "libs", "fonts", "assets"):
        src = src_content / folder
        if src.exists():
            log(f"Копирую content/{folder}/")
            shutil.copytree(src, staging_content / folder)

    # Иконка
    for fname in ("shanyrak_icon.svg",):
        src = src_content / fname
        if src.exists():
            shutil.copy2(src, staging_content / fname)

    # Плакаты — только нужных предметов
    posters_dst = staging_content / "posters"
    posters_dst.mkdir()
    for subj in subjects:
        src = src_content / "posters" / subj
        if not src.exists():
            log(f"⚠ Нет папки {src} — пропускаю")
            continue
        log(f"Копирую posters/{subj}/")
        shutil.copytree(src, posters_dst / subj)

    # Фильтрованный subjects.json
    with open(src_content / "subjects.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    include_set = set(subjects)
    filtered = [s for s in data.get("subjects", []) if s.get("id") in include_set]
    log(f"subjects.json: {len(data.get('subjects', []))} → {len(filtered)} предметов")
    with open(staging_content / "subjects.json", "w", encoding="utf-8") as f:
        json.dump({"subjects": filtered}, f, ensure_ascii=False, indent=2)

    # app_config.json
    app_cfg = {
        "skip_activation": skip_activation,
        "start_subject": start_subject,
        "window_title": display_title,
    }
    with open(staging_content / "app_config.json", "w", encoding="utf-8") as f:
        json.dump(app_cfg, f, ensure_ascii=False, indent=2)
    log(f"app_config.json: skip_activation={skip_activation}, start_subject={start_subject!r}")

    # icon.svg в корень staging
    icon_src = src_content / "shanyrak_icon.svg"
    if icon_src.exists():
        shutil.copy2(icon_src, staging / "icon.svg")

    log(f"✅ Staging готов: {staging_content}")
    return staging_content


# ────────────── Шаг 2. Иконка ──────────────

def make_ico(svg_path: Path, ico_path: Path, png_path: Path) -> None:
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    from PIL import Image

    if not QApplication.instance():
        QApplication(sys.argv)

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Не смог прочитать SVG: {svg_path}")

    size = 512
    img = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    img.save(str(png_path), "PNG")
    log(f"PNG иконка: {png_path}")

    pil = Image.open(png_path)
    pil.save(str(ico_path), format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    log(f"ICO иконка: {ico_path}")


# ────────────── Шаг 3. PyInstaller ──────────────

def run_pyinstaller(app_name: str, icon_path: Path, staging_content: Path,
                    subject_dir: Path) -> Path:
    staging = staging_content.parent
    work = BUILD_DIR
    dist = subject_dir  # builds/windows/<subject>/
    for d in (work, dist):
        d.mkdir(parents=True, exist_ok=True)

    target_app_dir = dist / app_name
    if target_app_dir.exists():
        shutil.rmtree(target_app_dir)
    spec = ROOT / f"{app_name}.spec"
    if spec.exists():
        spec.unlink()

    sep = ";" if platform.system() == "Windows" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean", "--onedir", "--windowed",
        f"--name={app_name}",
        f"--icon={icon_path}",
        f"--add-data={staging_content}{sep}content",
        f"--add-data={staging / 'icon.svg'}{sep}.",
        # ВАЖНО: license.dat НЕ запекаем в сборку — он создаётся при активации
        # в %APPDATA%/InteractivePosters/license.dat (см. licensing._user_data_dir).
        "--hidden-import=licensing",
        # Без --collect-submodules=PySide6: иначе тянет ВСЕ Qt модули.
        # Явно исключаем неиспользуемые (Qt3D, Quick, Charts, Multimedia, Pdf...).
        *[f"--exclude-module={m}" for m in PYSIDE6_EXCLUDES],
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(ROOT),
        str(ROOT / "main_app.py"),
    ]

    log("Запускаю PyInstaller…")
    log("  " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError("PyInstaller завершился с ошибкой")

    bundle = dist / app_name
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller не создал папку: {bundle}")

    log(f"✅ Бандл готов: {bundle}")
    return bundle


# ────────────── Шаг 3.5. Пост-очистка бандла ──────────────

# Языки, которые приложение реально поддерживает (locales/*.json).
# Только переводы из этих языков оставляем в Qt и в QtWebEngine.
KEEP_LANGS = {"ru", "kk", "kz", "en"}

# Qt-DLL, которые PyInstaller тащит автоматически, но приложение не использует.
# Имена без префикса/расширения (проверяем startswith).
# НЕ удаляем Qt6Qml*/Qt6Quick* — QtWebEngine зависит от них на уровне DLL.
# Основная экономия идёт от debug-ресурсов и переводов, а не от DLL.
UNUSED_QT_DLLS = (
    "Qt6Pdf",
    "Qt6VirtualKeyboard",
)


def _rm(path: Path) -> int:
    """Удаляет файл/папку и возвращает освобождённый размер (байты)."""
    if not path.exists():
        return 0
    try:
        if path.is_file():
            size = path.stat().st_size
            path.unlink()
            return size
        size = sum(p.stat().st_size for p in path.rglob("*") if p.is_file())
        shutil.rmtree(path)
        return size
    except Exception as e:
        log(f"  ⚠ Не удалось удалить {path}: {e}")
        return 0


def slim_bundle(bundle: Path) -> None:
    """Удаляет из готового PyInstaller-бандла всё, что не нужно для работы:
       debug-ресурсы Chromium, DevTools, неиспользуемые языки и Qt-DLL."""
    pyside = bundle / "_internal" / "PySide6"
    if not pyside.exists():
        log(f"⚠ Не нашёл {pyside}, пропускаю slim")
        return

    saved = 0
    log("Пост-очистка бандла…")

    # 1) Debug .pak / .bin (QtWebEngine devtools отладочные)
    res = pyside / "resources"
    if res.exists():
        for p in res.iterdir():
            n = p.name.lower()
            if n.endswith(".debug.pak") or n.endswith(".debug.bin"):
                saved += _rm(p)
            elif n.startswith("qtwebengine_devtools_resources"):
                # DevTools не используем (F12 заблокирован)
                saved += _rm(p)

    # 2) Неиспользуемые локали QtWebEngine
    locales = pyside / "translations" / "qtwebengine_locales"
    if locales.exists():
        for p in locales.iterdir():
            if not p.is_file():
                continue
            lang = p.stem.split("-")[0].lower()  # "ru" из "ru.pak", "en" из "en-GB.pak"
            if lang not in KEEP_LANGS:
                saved += _rm(p)

    # 3) Неиспользуемые .qm переводы Qt
    qm_dir = pyside / "translations"
    if qm_dir.exists():
        for p in qm_dir.iterdir():
            if not p.is_file() or p.suffix != ".qm":
                continue
            # Имена вида qtbase_de.qm, qt_gl.qm — берём суффикс после _
            stem = p.stem
            lang = stem.rsplit("_", 1)[-1].lower() if "_" in stem else stem.lower()
            if lang not in KEEP_LANGS:
                saved += _rm(p)

    # 4) Неиспользуемые Qt6*.dll и парные .pyd
    for p in pyside.iterdir():
        if not p.is_file():
            continue
        for prefix in UNUSED_QT_DLLS:
            if p.name.startswith(prefix) and (p.suffix.lower() in (".dll", ".pyd")):
                saved += _rm(p)
                break

    # 5) opengl32sw.dll — программный OpenGL ~20 МБ. Удаляем: на современных
    # машинах QtWebEngine использует аппаратный/ANGLE. Если на старых машинах
    # будут проблемы — вернуть в список.
    sw_gl = pyside / "opengl32sw.dll"
    if sw_gl.exists():
        saved += _rm(sw_gl)

    log(f"✅ Slim освободил {saved / 1024 / 1024:.1f} МБ")


# ────────────── Шаг 4. Inno Setup ──────────────

def find_iscc() -> str | None:
    for c in (
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ):
        if Path(c).exists():
            return c
    return None


def write_iss(app_name: str, display_name: str, bundle: Path, icon_path: Path,
              subject_dir: Path) -> Path:
    iss_path = ROOT / f"{app_name}.iss"
    installer_dist = subject_dir  # builds/windows/<subject>/
    installer_dist.mkdir(parents=True, exist_ok=True)

    # Уникальный AppId на основе имени приложения
    app_id = f"{{{{B7B0B002-{app_name[:8].upper()}-4D2A-9E2A-INTERACTPOSTERS}}}}"

    iss = f"""; Автосгенерированный скрипт Inno Setup — {app_name}
#define MyAppName "{display_name}"
#define MyAppVersion "{APP_VERSION}"
#define MyAppPublisher "{APP_PUBLISHER}"
#define MyAppExeName "{app_name}.exe"

[Setup]
AppId={app_id}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\{app_name}
DefaultGroupName={{#MyAppName}}
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}
OutputDir={installer_dist}
OutputBaseFilename={app_name}-Setup-{APP_VERSION}
Compression=lzma2/ultra
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
SetupIconFile={icon_path}
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Дополнительные значки:"; Flags: checkedonce

[Files]
Source: "{bundle}\\*"; DestDir: "{{app}}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{{group}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"
Name: "{{group}}\\Удалить {{#MyAppName}}"; Filename: "{{uninstallexe}}"
Name: "{{autodesktop}}\\{{#MyAppName}}"; Filename: "{{app}}\\{{#MyAppExeName}}"; Tasks: desktopicon

[Run]
Filename: "{{app}}\\{{#MyAppExeName}}"; Description: "Запустить {{#MyAppName}}"; Flags: nowait postinstall skipifsilent
"""
    iss_path.write_text(iss, encoding="utf-8")
    log(f"Inno-скрипт: {iss_path}")
    return iss_path


def run_inno(app_name: str, iss_path: Path) -> Path | None:
    iscc = find_iscc()
    if not iscc:
        log("⚠ Inno Setup не найден, пропускаю создание установщика")
        return None
    log(f"Запускаю ISCC: {iscc}")
    result = subprocess.run([iscc, str(iss_path)], cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError("ISCC завершился с ошибкой")
    # Ищем установщик в папке предмета (Inno кладёт туда же, куда OutputDir)
    setup = None
    for d in BUILDS_DIR.rglob(f"{app_name}-Setup-{APP_VERSION}.exe"):
        setup = d
        break
    if setup and setup.exists():
        log(f"✅ Установщик: {setup} ({setup.stat().st_size / 1024 / 1024:.1f} MB)")
    return setup


# ────────────── Сборка одного «пакета» ──────────────

def build_one(subjects: list[str], *, app_name: str, display_title: str,
              start_subject: str | None, skip_activation: bool,
              no_installer: bool) -> bool:
    """Полный цикл: staging → ico → pyinstaller → inno."""
    log(f"\n{'='*60}")
    log(f"Собираю: {app_name}")
    log(f"Предметы: {', '.join(subjects)}")
    log(f"{'='*60}")

    # Папка для этого предмета: builds/windows/<subject>/
    first_subj = subjects[0] if len(subjects) == 1 else "all"
    subject_dir = BUILDS_DIR / first_subj
    subject_dir.mkdir(parents=True, exist_ok=True)

    try:
        staging_content = prepare_staging(
            subjects,
            start_subject=start_subject,
            skip_activation=skip_activation,
            display_title=display_title,
        )

        icon_svg = ROOT / "content" / "shanyrak_icon.svg"
        icon_png = BUILD_DIR / "icon.png"
        icon_ico = BUILD_DIR / "icon.ico"
        BUILD_DIR.mkdir(exist_ok=True)
        make_ico(icon_svg, icon_ico, icon_png)

        bundle = run_pyinstaller(app_name, icon_ico, staging_content, subject_dir)

        # Удаляем из бандла то, что PyInstaller тащит "на всякий случай"
        slim_bundle(bundle)

        if no_installer:
            log(f"Пропускаю Inno Setup (--no-installer). Готовая папка: {bundle}")
        else:
            iss = write_iss(app_name, display_title, bundle, icon_ico, subject_dir)
            run_inno(app_name, iss)

        log(f"📂 Результат: {subject_dir}")
        return True
    except Exception as e:
        log(f"❌ Ошибка при сборке {app_name}: {e}")
        return False


# ────────────── CLI ──────────────

def list_subjects() -> None:
    print("\n📚 Доступные предметы для сборки:")
    print("-" * 55)
    for subj in ALL_SUBJECTS:
        aliases = [k for k, v in ALIASES.items() if v == subj]
        alias_str = f"  (алиасы: {', '.join(aliases)})" if aliases else ""
        name = DISPLAY_NAMES.get(subj, subj)
        poster_dir = ROOT / "content" / "posters" / subj
        count = len(list(poster_dir.glob("*.html"))) if poster_dir.exists() else 0
        print(f"  {subj:<16} {count:>3} плакатов  {name}{alias_str}")
    print("-" * 55)
    print("  allsubjects    — один EXE со всеми предметами")
    print("  all            — собрать 11 отдельных EXE\n")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Универсальная сборка Windows EXE с выбором предметов",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("subjects", nargs="*", help="Предметы (physics, chem, all, allsubjects…)")
    ap.add_argument("--list", "-l", action="store_true", help="Показать доступные предметы")
    ap.add_argument("--no-installer", action="store_true", help="Не запускать Inno Setup")
    ap.add_argument("--clean", action="store_true", help="Очистить build/ и dist/ перед сборкой")
    ap.add_argument("--skip-activation", action="store_true",
                    help="Пропустить окно активации (по умолчанию — показывать)")
    args = ap.parse_args()

    if args.list:
        list_subjects()
        return

    if not args.subjects:
        ap.print_help()
        print("\nПримеры:")
        print("  python build_windows.py physics")
        print("  python build_windows.py chem math --skip-activation")
        print("  python build_windows.py all")
        print("  python build_windows.py allsubjects --no-installer")
        return

    if args.clean:
        for d in (BUILD_DIR, BUILDS_DIR, ROOT / "_build_staging"):
            if d.exists():
                log(f"Удаляю {d}")
                shutil.rmtree(d)

    # Разбираем список предметов
    raw = []
    for a in args.subjects:
        resolved = ALIASES.get(a, a)
        if resolved in ALL_SUBJECTS or resolved in ("all", "allsubjects"):
            raw.append(resolved)
        else:
            print(f"⚠ Неизвестный предмет: {a}")
            print(f"  Запустите: python build_windows.py --list")
            return

    # Определяем задачи сборки: список (subjects, app_name, display, start_subject)
    tasks: list[tuple[list[str], str, str, str | None]] = []

    if "all" in raw:
        # Каждый предмет — отдельный EXE
        for subj in ALL_SUBJECTS:
            tasks.append(
                ([subj], app_name_for(subj), display_name_for(subj), subj)
            )
    elif "allsubjects" in raw:
        # Один EXE со всеми
        tasks.append(
            (ALL_SUBJECTS[:], "InteractivePosters-All",
             "Интерактивные плакаты — Все предметы", None)
        )
    else:
        # Каждый указанный предмет — отдельный EXE
        for subj in raw:
            tasks.append(
                ([subj], app_name_for(subj), display_name_for(subj), subj)
            )

    success = 0
    failed = 0
    for subjects, name, display, start_subj in tasks:
        ok = build_one(
            subjects,
            app_name=name,
            display_title=display,
            start_subject=start_subj,
            skip_activation=args.skip_activation,
            no_installer=args.no_installer,
        )
        if ok:
            success += 1
        else:
            failed += 1

    print(f"\n{'='*60}")
    print(f"✅ Успешно: {success}  ❌ Ошибок: {failed}")
    if success > 0:
        print(f"📁 Результат: {BUILDS_DIR}")
    print(f"{'='*60}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ ОШИБКА: {e}")
        sys.exit(1)
