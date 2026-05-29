# -*- coding: utf-8 -*-
"""
Генератор лицензионных ключей для «Интерактивных плакатов».

ВНИМАНИЕ: Этот файл НЕ включается в сборку приложения!
Используется ТОЛЬКО разработчиком для генерации ключей.

Использование:
    python keygen.py init                                         # Создать секретный ключ (один раз!)
    python keygen.py gen informatics 42 --device A3F2B1C8E4D71029 # Ключ привязан к устройству
    python keygen.py gen physics 7 --months 24 --device DEADBEEF12345678
    python keygen.py verify XXXX-XXXX-XXXX-XXXX-XXXX --device A3F2B1C8E4D71029
    python keygen.py list                                         # Показать все выданные ключи
    python keygen.py embed                                        # Вывести код для встраивания секрета
"""

import argparse
import base64
import hashlib
import hmac
import os
import sqlite3
import struct
import sys
from datetime import datetime

SECRETS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets.key")
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "keys.db")

# Маппинг предметов → индексы (4 бита, 0–15)
SUBJECTS = {
    'physics': 0,
    'mathematics': 1,
    'biology': 2,
    'chemistry': 3,
    'geography': 4,
    'informatics': 5,
    'historykaz': 6,
    'worldhistory': 7,
    'kazakhlang': 8,
    'russianlang': 9,
    'englishlang': 10,
}
SUBJECTS_REV = {v: k for k, v in SUBJECTS.items()}


# ─── Секретный ключ ────────────────────────────────────────────

def load_secret() -> bytes:
    """Загрузить секретный ключ из файла."""
    if not os.path.exists(SECRETS_FILE):
        print(f"❌ Файл {SECRETS_FILE} не найден.")
        print(f"   Запустите: python keygen.py init")
        sys.exit(1)
    with open(SECRETS_FILE, 'rb') as f:
        secret = f.read()
    if len(secret) != 32:
        print(f"❌ Некорректный секретный ключ (ожидается 32 байта, получено {len(secret)})")
        sys.exit(1)
    return secret


def cmd_init(_args):
    """Создать новый секретный ключ."""
    if os.path.exists(SECRETS_FILE):
        print(f"⚠️  Файл {SECRETS_FILE} уже существует!")
        print(f"   Если перезаписать — ВСЕ ранее выданные ключи станут невалидными.")
        ans = input("   Перезаписать? (yes/no): ").strip().lower()
        if ans != 'yes':
            print("   Отменено.")
            return
    secret = os.urandom(32)
    with open(SECRETS_FILE, 'wb') as f:
        f.write(secret)
    print(f"✅ Секретный ключ создан: {SECRETS_FILE}")
    print(f"   Длина: 256 бит")
    print(f"")
    print(f"   ⚠️  ВАЖНО:")
    print(f"   1. Храните этот файл в безопасности")
    print(f"   2. Сделайте резервную копию")
    print(f"   3. Без него невозможно генерировать ключи")
    print(f"   4. НЕ включайте его в сборку приложения")


# ─── Генерация / валидация ключей ──────────────────────────────

def encode_key(subject_idx: int, client_id: int, duration_months: int,
               flags: int, secret: bytes, device_id: str = '') -> str:
    """
    Создаёт подписанный лицензионный ключ, привязанный к device_id.

    Формат payload (4 байта, big-endian uint32):
        биты 31–28 : subject_idx      (4 бита,  0–15)
        биты 27–12 : client_id        (16 бит,  0–65535)
        биты 11–4  : duration_months   (8 бит,  1–255)
        биты 3–0   : flags            (4 бита,  зарезервировано)

    Формат ключа: payload(4 байт) + HMAC-SHA256(payload + device_id)[:8] = 12 байт
    Base32 → 20 символов → XXXX-XXXX-XXXX-XXXX-XXXX

    device_id включается в HMAC — ключ валиден ТОЛЬКО на конкретном устройстве.
    """
    val = ((subject_idx & 0xF) << 28) | \
          ((client_id & 0xFFFF) << 12) | \
          ((duration_months & 0xFF) << 4) | \
          (flags & 0xF)
    payload = struct.pack('>I', val)
    # HMAC подписывает payload + device_id → ключ привязан к машине
    hmac_data = payload + device_id.upper().encode()
    sig = hmac.new(secret, hmac_data, hashlib.sha256).digest()[:8]
    raw = payload + sig  # 12 байт
    encoded = base64.b32encode(raw).decode().rstrip('=')
    # Форматируем: XXXX-XXXX-XXXX-XXXX-XXXX
    return '-'.join(encoded[i:i+4] for i in range(0, 20, 4))


def decode_key(key_str: str, secret: bytes, device_id: str = '') -> tuple:
    """
    Проверяет и декодирует лицензионный ключ.
    device_id используется для проверки HMAC-привязки к устройству.
    Возвращает (data_dict, error_string). При ошибке data_dict = None.
    """
    clean = key_str.replace('-', '').replace(' ', '').upper()
    if len(clean) != 20:
        return None, "Неверная длина ключа (ожидается 20 символов без дефисов)"

    # Добавляем padding для base32
    padded = clean + '=' * ((8 - len(clean) % 8) % 8)
    try:
        raw = base64.b32decode(padded)
    except Exception:
        return None, "Неверные символы в ключе"

    if len(raw) != 12:
        return None, "Неверный размер данных"

    payload, sig = raw[:4], raw[4:]

    # Проверяем подпись (включая device_id)
    hmac_data = payload + device_id.upper().encode()
    expected = hmac.new(secret, hmac_data, hashlib.sha256).digest()[:8]
    if not hmac.compare_digest(sig, expected):
        return None, "Ключ не подходит для этого устройства"

    # Декодируем payload
    val = struct.unpack('>I', payload)[0]
    return {
        'subject_idx': (val >> 28) & 0xF,
        'subject': SUBJECTS_REV.get((val >> 28) & 0xF, 'unknown'),
        'client_id': (val >> 12) & 0xFFFF,
        'duration_months': (val >> 4) & 0xFF,
        'flags': val & 0xF,
    }, None


# ─── База данных выданных ключей ───────────────────────────────

def _init_db():
    """Создаёт таблицу если не существует."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key_str TEXT UNIQUE NOT NULL,
            subject TEXT NOT NULL,
            client_id INTEGER NOT NULL,
            duration_months INTEGER NOT NULL,
            flags INTEGER DEFAULT 0,
            device_id TEXT DEFAULT '',
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
    """)
    # Добавляем колонку device_id если её нет (миграция старых БД)
    try:
        conn.execute("ALTER TABLE keys ADD COLUMN device_id TEXT DEFAULT ''")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # колонка уже есть
    conn.commit()
    return conn


def _save_key(conn, key_str, subject, client_id, duration_months, flags,
              device_id='', note=''):
    """Сохраняет ключ в БД."""
    conn.execute(
        "INSERT INTO keys (key_str, subject, client_id, duration_months, flags, device_id, note, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (key_str, subject, client_id, duration_months, flags, device_id, note,
         datetime.now().isoformat(timespec='seconds'))
    )
    conn.commit()


# ─── Команды CLI ───────────────────────────────────────────────

def cmd_gen(args):
    """Сгенерировать ключ."""
    subject = args.subject.lower()
    if subject not in SUBJECTS:
        print(f"❌ Неизвестный предмет: {subject}")
        print(f"   Доступные: {', '.join(sorted(SUBJECTS.keys()))}")
        sys.exit(1)

    client_id = args.client_id
    if not (0 <= client_id <= 65535):
        print(f"❌ client_id должен быть 0–65535")
        sys.exit(1)

    months = args.months
    if not (1 <= months <= 255):
        print(f"❌ months должен быть 1–255")
        sys.exit(1)

    device_id = (args.device or '').strip().upper()
    if not device_id:
        print(f"❌ Не указан --device (Device ID целевого устройства)")
        print(f"   Пользователь видит свой Device ID на экране активации.")
        sys.exit(1)
    if len(device_id) != 16:
        print(f"❌ Device ID должен быть 16 hex-символов (получено {len(device_id)}: '{device_id}')")
        sys.exit(1)

    secret = load_secret()
    key_str = encode_key(SUBJECTS[subject], client_id, months, 0, secret, device_id)

    # Сохраняем в БД
    conn = _init_db()
    note = args.note or ''
    _save_key(conn, key_str, subject, client_id, months, 0, device_id, note)
    conn.close()

    print(f"")
    print(f"  🔑  {key_str}")
    print(f"")
    print(f"  Предмет:     {subject}")
    print(f"  Клиент:      #{client_id}")
    print(f"  Устройство:  {device_id}")
    print(f"  Срок:        {months} мес. (с момента активации)")
    if note:
        print(f"  Заметка:     {note}")
    print(f"  Создан:      {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"")


def cmd_verify(args):
    """Проверить ключ."""
    device_id = (args.device or '').strip().upper()
    if not device_id:
        print(f"❌ Не указан --device (Device ID для проверки привязки)")
        sys.exit(1)

    secret = load_secret()
    data, err = decode_key(args.key, secret, device_id)
    if err:
        print(f"  ❌ {err}")
        sys.exit(1)
    print(f"  ✅ Ключ валидный для устройства {device_id}")
    print(f"")
    print(f"  Предмет:     {data['subject']}")
    print(f"  Клиент:      #{data['client_id']}")
    print(f"  Срок:        {data['duration_months']} мес.")
    print(f"  Устройство:  {device_id}")
    print(f"  Флаги:       {data['flags']}")


def cmd_list(_args):
    """Показать все выданные ключи."""
    conn = _init_db()
    rows = conn.execute(
        "SELECT key_str, subject, client_id, duration_months, note, created_at "
        "FROM keys ORDER BY id DESC"
    ).fetchall()
    conn.close()

    if not rows:
        print("  Ключей пока нет.")
        return

    print(f"  {'Ключ':<27} {'Предмет':<14} {'Клиент':>7} {'Мес.':>5}  {'Дата':<20} {'Заметка'}")
    print(f"  {'─'*27} {'─'*14} {'─'*7} {'─'*5}  {'─'*20} {'─'*20}")
    for key_str, subj, cid, dur, note, created in rows:
        print(f"  {key_str:<27} {subj:<14} {'#'+str(cid):>7} {dur:>5}  {created:<20} {note or ''}")
    print(f"\n  Всего: {len(rows)} ключей")


def cmd_embed(_args):
    """Вывести обфусцированный секрет для встраивания в licensing.py."""
    secret = load_secret()
    mask = os.urandom(32)
    obfuscated = bytes(a ^ b for a, b in zip(secret, mask))

    print("# Вставьте эти строки в licensing.py")
    print("# Секрет = bytes(a ^ b for a, b in zip(_MASK, _KDATA))")
    print(f"_MASK  = {list(mask)}")
    print(f"_KDATA = {list(obfuscated)}")
    print()
    print("# Проверка (в keygen, не в приложении):")
    recovered = bytes(a ^ b for a, b in zip(mask, obfuscated))
    print(f"# Совпадает: {recovered == secret}")


# ─── Точка входа ───────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='Генератор лицензионных ключей — Интерактивные плакаты',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python keygen.py init                          Создать секретный ключ
  python keygen.py gen informatics 42            12 мес., клиент #42
  python keygen.py gen physics 7 --months 24     24 мес., клиент #7
  python keygen.py verify XXXX-XXXX-XXXX-XXXX-XXXX
  python keygen.py list
  python keygen.py embed                         Код для licensing.py
        """
    )
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('init', help='Создать секретный ключ (один раз!)')

    p_gen = sub.add_parser('gen', help='Сгенерировать ключ')
    p_gen.add_argument('subject', help='Предмет (informatics, physics, ...)')
    p_gen.add_argument('client_id', type=int, help='ID клиента (0–65535)')
    p_gen.add_argument('--device', type=str, required=True, help='Device ID целевого устройства (16 hex)')
    p_gen.add_argument('--months', type=int, default=12, help='Срок в месяцах (по умолчанию 12)')
    p_gen.add_argument('--note', type=str, default='', help='Заметка (название школы и т.д.)')

    p_ver = sub.add_parser('verify', help='Проверить ключ')
    p_ver.add_argument('key', help='Ключ в формате XXXX-XXXX-XXXX-XXXX-XXXX')
    p_ver.add_argument('--device', type=str, required=True, help='Device ID для проверки привязки')

    sub.add_parser('list', help='Показать все выданные ключи')
    sub.add_parser('embed', help='Вывести код для встраивания секрета в licensing.py')

    args = parser.parse_args()

    commands = {
        'init': cmd_init,
        'gen': cmd_gen,
        'verify': cmd_verify,
        'list': cmd_list,
        'embed': cmd_embed,
    }

    if args.command in commands:
        commands[args.command](args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
