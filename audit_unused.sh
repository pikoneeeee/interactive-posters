#!/bin/bash
set -e

MODE="${1:-}"   # пусто = только отчёт, --move = перенос в _unused_trash

python3 - <<'PY'
import re, os, shutil, sys
from pathlib import Path

proj = Path(".").resolve()

content = proj / "content"
posters = content / "posters"
if not posters.exists():
    print("❌ Не найдено content/posters. Запусти из папки InteractivePosters/")
    sys.exit(1)

reports = proj / "reports"
reports.mkdir(exist_ok=True)

trash = proj / "_unused_trash"
move_mode = ("--move" in sys.argv)

# Что считаем "ассетами" (можешь расширить)
ASSET_EXT = {".png",".jpg",".jpeg",".gif",".webp",".svg",".ico",
             ".css",".js",".json",
             ".ttf",".otf",".woff",".woff2",
             ".mp3",".wav",".mp4",".webm",
             ".pdf"}

# Где искать кандидатов на удаление
CANDIDATE_DIRS = [
    content,            # всё внутри content (осторожно, но мы фильтруем по расширению)
]

# Где искать ссылки (источники)
SOURCE_DIRS = [
    posters,
    content,            # чтобы поймать ссылки из общих css/js/json
]

# Файлы, в которых ищем ссылки (текстовые)
SOURCE_TEXT_EXT = {".html",".htm",".css",".js",".json",".txt",".md",".py"}
ALWAYS_KEEP = {
    (content / "subjects.json").resolve(),
    (content / "shanyrak_icon.svg").resolve(),
    (content / "locales" / "ru.json").resolve(),
    (content / "locales" / "kz.json").resolve(),
    (content / "locales" / "en.json").resolve(),
}

# --- сбор всех ассетов-кандидатов ---
candidates = []
for base in CANDIDATE_DIRS:
    for p in base.rglob("*"):
        if p.is_file() and p.suffix.lower() in ASSET_EXT:
            # не трогаем отчёты/корзину/бэкапы
            if "_unused_trash" in p.parts or "reports" in p.parts or "backup" in p.parts:
                continue
            candidates.append(p)

# --- собираем все ссылки из исходников ---
src_href_re = re.compile(r'''(?:src|href)\s*=\s*["']([^"']+)["']''', re.I)
css_url_re   = re.compile(r'''url\(\s*(['"]?)(.*?)\1\s*\)''', re.I)

def norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    u = u.split("#")[0].split("?")[0].strip()
    return u

def is_ignorable(u: str) -> bool:
    lu = u.lower()
    return (not u or u.startswith("#") or
            lu.startswith(("http:","https:","data:","mailto:","tel:","javascript:","about:","qrc:","qt:")))

used = set()

# Сканируем исходники, вытаскиваем ссылки и пытаемся резолвить в файлы
sources_scanned = 0
for base in SOURCE_DIRS:
    for f in base.rglob("*"):
        if not f.is_file():
            continue
        if f.suffix.lower() not in SOURCE_TEXT_EXT:
            continue
        sources_scanned += 1
        txt = f.read_text(encoding="utf-8", errors="ignore")

        urls = []
        urls += [norm_url(m.group(1)) for m in src_href_re.finditer(txt)]
        urls += [norm_url(m.group(2)) for m in css_url_re.finditer(txt)]

        for u in urls:
            if is_ignorable(u):
                continue

            # абсолютный путь внутри content (если начинается с /)
            if u.startswith("/"):
                target = (content / u.lstrip("/")).resolve()
            else:
                target = (f.parent / u).resolve()

            # если ссылка ведёт на существующий файл — помечаем used
            if target.exists() and target.is_file():
                used.add(target)

# --- вычисляем неиспользуемое ---
unused = [p for p in candidates if p not in used and p.resolve() not in ALWAYS_KEEP]


# --- отчёты ---
unused_txt = reports / "unused_files.txt"
used_txt   = reports / "used_files_count.txt"

unused_txt.write_text("\n".join(str(p.relative_to(proj)) for p in sorted(unused)), encoding="utf-8")
used_txt.write_text(
    f"Sources scanned: {sources_scanned}\n"
    f"Candidates: {len(candidates)}\n"
    f"Used: {len(used)}\n"
    f"Unused: {len(unused)}\n",
    encoding="utf-8"
)

print("✅ Audit complete")
print(used_txt.read_text(encoding="utf-8").strip())
print(f"📄 Отчёт: {unused_txt}")

# --- безопасное перемещение в корзину ---
if move_mode:
    trash.mkdir(exist_ok=True)
    moved = 0
    for p in unused:
        rel = p.relative_to(proj)
        dst = trash / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        # если файл уже там есть — добавим суффикс
        if dst.exists():
            dst = dst.with_name(dst.stem + "_dup" + dst.suffix)
        shutil.move(str(p), str(dst))
        moved += 1
    print(f"🗑 Перемещено в {trash}: {moved} файлов (НЕ удалено навсегда)")

PY

