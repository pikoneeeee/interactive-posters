# -*- coding: utf-8 -*-
"""
Сборка Windows-установщика только с информатикой.

Шаги:
1. Собирает staging-папку с контентом: только informatics.
2. Генерирует иконку (.ico) из content/shanyrak_icon.svg через PySide6.
3. Запускает PyInstaller (--onedir --windowed).
4. Если установлен Inno Setup — собирает Setup.exe.

Использование:
    python build_windows_informatics.py
    python build_windows_informatics.py --no-installer   # только EXE, без Inno Setup
    python build_windows_informatics.py --clean          # удалить build/ и staging перед сборкой
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# Принудительный UTF-8 на Windows (консоль cp1251 ломается на юникод-символах)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")

ROOT = Path(__file__).resolve().parent
STAGING = ROOT / "_build_staging"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
APP_NAME = "InteractivePosters-Informatics"
APP_DISPLAY = "Интерактивные плакаты — Информатика"
APP_VERSION = "1.1.0"
APP_PUBLISHER = "DigiTouch"

# Какие предметы попадают в билд
INCLUDE_SUBJECTS = {"informatics"}
# С какого предмета сразу открывать список плакатов (None — показывать экран выбора)
START_SUBJECT = "informatics"
# Пропускать окно активации
SKIP_ACTIVATION = True


def log(msg: str) -> None:
    print(f"[build] {msg}")


# ---------- Шаг 1. Staging ----------

def prepare_staging(clean: bool = False) -> Path:
    """Готовит _build_staging/content/ с нужными плакатами и фильтрованным subjects.json."""
    if clean and STAGING.exists():
        log(f"Очищаю staging: {STAGING}")
        shutil.rmtree(STAGING)
    staging_content = STAGING / "content"
    if staging_content.exists():
        shutil.rmtree(staging_content)
    staging_content.mkdir(parents=True)

    src_content = ROOT / "content"

    # Общие папки целиком
    for folder in ("locales", "templates", "libs", "fonts", "assets"):
        src = src_content / folder
        if src.exists():
            log(f"Копирую content/{folder}/")
            shutil.copytree(src, staging_content / folder)

    # Иконка (используется приложением в runtime)
    for fname in ("shanyrak_icon.svg",):
        src = src_content / fname
        if src.exists():
            shutil.copy2(src, staging_content / fname)

    # Плакаты — только нужных предметов
    posters_dst = staging_content / "posters"
    posters_dst.mkdir()
    for subj in INCLUDE_SUBJECTS:
        src = src_content / "posters" / subj
        if not src.exists():
            log(f"⚠ Нет папки {src} — пропускаю")
            continue
        log(f"Копирую posters/{subj}/")
        shutil.copytree(src, posters_dst / subj)

    # Фильтрованный subjects.json
    with open(src_content / "subjects.json", "r", encoding="utf-8") as f:
        data = json.load(f)
    filtered = [s for s in data.get("subjects", []) if s.get("id") in INCLUDE_SUBJECTS]
    log(f"subjects.json: {len(data.get('subjects', []))} → {len(filtered)} предметов")
    with open(staging_content / "subjects.json", "w", encoding="utf-8") as f:
        json.dump({"subjects": filtered}, f, ensure_ascii=False, indent=2)

    # app_config.json — управляет поведением приложения в билде
    app_cfg = {
        "skip_activation": SKIP_ACTIVATION,
        "start_subject": START_SUBJECT,
        "window_title": APP_DISPLAY,
    }
    with open(staging_content / "app_config.json", "w", encoding="utf-8") as f:
        json.dump(app_cfg, f, ensure_ascii=False, indent=2)
    log(f"app_config.json: skip_activation={SKIP_ACTIVATION}, start_subject={START_SUBJECT!r}")

    # icon.svg на корень staging — приложение грузит его из BASE_DIR
    icon_src = src_content / "shanyrak_icon.svg"
    if icon_src.exists():
        shutil.copy2(icon_src, STAGING / "icon.svg")

    log(f"✅ Staging готов: {staging_content}")
    return staging_content


# ---------- Шаг 2. Иконка ----------

def make_ico(svg_path: Path, ico_path: Path, png_path: Path) -> None:
    """Рендерит SVG → PNG через PySide6 и конвертирует в ICO через Pillow."""
    from PySide6.QtCore import QSize, Qt
    from PySide6.QtGui import QImage, QPainter, QColor
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtWidgets import QApplication
    from PIL import Image

    if not QApplication.instance():
        QApplication(sys.argv)

    renderer = QSvgRenderer(str(svg_path))
    if not renderer.isValid():
        raise RuntimeError(f"Не смог прочитать SVG: {svg_path}")

    # Рендерим в 512×512 с белым фоном (чтобы не было прозрачности в ICO)
    size = 512
    img = QImage(QSize(size, size), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()

    img.save(str(png_path), "PNG")
    log(f"PNG иконка: {png_path}")

    # В ICO кладём несколько размеров
    pil = Image.open(png_path)
    pil.save(str(ico_path), format="ICO",
             sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    log(f"ICO иконка: {ico_path}")


# ---------- Шаг 3. PyInstaller ----------

def run_pyinstaller(icon_path: Path, staging_content: Path) -> Path:
    """Собирает onedir-бандл через PyInstaller. Возвращает путь к dist/<APP_NAME>/."""
    work = BUILD_DIR
    dist = DIST_DIR
    for d in (work, dist):
        d.mkdir(parents=True, exist_ok=True)

    # Чистим предыдущую сборку этого приложения
    target_app_dir = dist / APP_NAME
    if target_app_dir.exists():
        shutil.rmtree(target_app_dir)
    spec = ROOT / f"{APP_NAME}.spec"
    if spec.exists():
        spec.unlink()

    add_data_sep = ";" if platform.system() == "Windows" else ":"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onedir",
        "--windowed",
        f"--name={APP_NAME}",
        f"--icon={icon_path}",
        f"--add-data={staging_content}{add_data_sep}content",
        f"--add-data={STAGING / 'icon.svg'}{add_data_sep}.",
        f"--add-data={ROOT / 'license.dat'}{add_data_sep}.",
        # licensing.py — отдельный модуль, PyInstaller найдёт его сам через import,
        # но добавим в hidden-imports на всякий случай
        "--hidden-import=licensing",
        "--collect-submodules=PySide6",
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

    bundle = dist / APP_NAME
    if not bundle.exists():
        raise RuntimeError(f"PyInstaller не создал папку: {bundle}")

    log(f"✅ Бандл готов: {bundle}")
    return bundle


# ---------- Шаг 4. Inno Setup ----------

def find_iscc() -> str | None:
    candidates = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None


def write_iss(bundle: Path, icon_path: Path) -> Path:
    """Создаёт .iss файл для Inno Setup."""
    iss_path = ROOT / f"{APP_NAME}.iss"
    installer_dist = DIST_DIR / "installer"
    installer_dist.mkdir(exist_ok=True)

    iss = f"""; Автосгенерированный скрипт Inno Setup
#define MyAppName "{APP_DISPLAY}"
#define MyAppVersion "{APP_VERSION}"
#define MyAppPublisher "{APP_PUBLISHER}"
#define MyAppExeName "{APP_NAME}.exe"

[Setup]
AppId={{{{B7B0B002-INF2-4D2A-9E2A-INTERACTPOSTERS}}}}
AppName={{#MyAppName}}
AppVersion={{#MyAppVersion}}
AppPublisher={{#MyAppPublisher}}
DefaultDirName={{autopf}}\\InteractivePosters-Informatics
DefaultGroupName={{#MyAppName}}
UninstallDisplayIcon={{app}}\\{{#MyAppExeName}}
OutputDir={installer_dist}
OutputBaseFilename={APP_NAME}-Setup-{APP_VERSION}
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


def run_inno(iss_path: Path) -> Path | None:
    iscc = find_iscc()
    if not iscc:
        log("⚠ Inno Setup не найден, пропускаю создание установщика")
        return None
    log(f"Запускаю ISCC: {iscc}")
    result = subprocess.run([iscc, str(iss_path)], cwd=str(ROOT))
    if result.returncode != 0:
        raise RuntimeError("ISCC завершился с ошибкой")
    # Итоговый файл
    setup = DIST_DIR / "installer" / f"{APP_NAME}-Setup-{APP_VERSION}.exe"
    if setup.exists():
        log(f"✅ Установщик: {setup} ({setup.stat().st_size / 1024 / 1024:.1f} MB)")
    return setup


# ---------- main ----------

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-installer", action="store_true", help="Не запускать Inno Setup")
    ap.add_argument("--clean", action="store_true", help="Полная очистка перед сборкой")
    args = ap.parse_args()

    if args.clean:
        for d in (BUILD_DIR, DIST_DIR, STAGING):
            if d.exists():
                log(f"Удаляю {d}")
                shutil.rmtree(d)

    staging_content = prepare_staging(clean=args.clean)

    icon_svg = ROOT / "content" / "shanyrak_icon.svg"
    icon_png = BUILD_DIR / "icon.png"
    icon_ico = BUILD_DIR / "icon.ico"
    BUILD_DIR.mkdir(exist_ok=True)
    make_ico(icon_svg, icon_ico, icon_png)

    bundle = run_pyinstaller(icon_ico, staging_content)

    if args.no_installer:
        log("Пропускаю Inno Setup (--no-installer)")
        log(f"Готовая папка: {bundle}")
        return

    iss = write_iss(bundle, icon_ico)
    setup = run_inno(iss)
    if setup:
        log("\n🎉 Готово!")
        log(f"Установщик: {setup}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log(f"❌ ОШИБКА: {e}")
        sys.exit(1)
