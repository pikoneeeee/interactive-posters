# -*- coding: utf-8 -*-
"""
Система лицензирования — Интерактивные плакаты.

Проверка HMAC-подписанных ключей, активация с привязкой к устройству,
шифрованный license.dat, срок действия от момента активации,
защита от перевода системных часов назад.
"""

import base64
import hashlib
import hmac
import json
import os
import platform
import struct
import subprocess
import sys
import time
from datetime import datetime, timedelta

# ─── Обфусцированный секретный ключ ────────────────────────────
# Генерируется командой: python keygen.py embed
# Секрет = bytes(a ^ b for a, b in zip(_MASK, _KDATA))
_MASK  = [0, 4, 51, 226, 213, 62, 45, 201, 14, 126, 242, 86, 239, 239, 194, 85, 33, 129, 246, 245, 37, 190, 237, 248, 147, 87, 202, 192, 203, 201, 17, 91]
_KDATA = [89, 136, 108, 16, 86, 143, 66, 45, 110, 88, 175, 143, 29, 158, 55, 107, 170, 111, 116, 154, 64, 224, 210, 220, 4, 150, 168, 123, 166, 18, 231, 195]

def _get_secret() -> bytes:
    return bytes(a ^ b for a, b in zip(_MASK, _KDATA))

# ─── Маппинг предметов ─────────────────────────────────────────
SUBJECTS_REV = {
    0: 'physics', 1: 'mathematics', 2: 'biology', 3: 'chemistry',
    4: 'geography', 5: 'informatics', 6: 'historykaz', 7: 'worldhistory',
    8: 'kazakhlang', 9: 'russianlang', 10: 'englishlang',
}

# ─── Пути ───────────────────────────────────────────────────────
if getattr(sys, 'frozen', False):
    _BASE_DIR = sys._MEIPASS
else:
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _user_data_dir() -> str:
    """Папка для хранения license.dat в пользовательском профиле.

    Хранить лицензию рядом с EXE нельзя:
      - после установки в Program Files папка read-only без админа;
      - PyInstaller _MEIPASS — это временная распаковка, не для записи.
    """
    if sys.platform == 'win32':
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
    elif sys.platform == 'darwin':
        base = os.path.expanduser('~/Library/Application Support')
    else:
        base = os.environ.get('XDG_CONFIG_HOME') or os.path.expanduser('~/.config')
    d = os.path.join(base, 'InteractivePosters')
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


LICENSE_FILE = os.path.join(_user_data_dir(), "license.dat")

# Максимально допустимый откат часов (часы). Если часы откатили больше —
# считаем попыткой обхода.
_MAX_CLOCK_DRIFT_HOURS = 24


# ─── Device ID ──────────────────────────────────────────────────

def get_device_id() -> str:
    """Уникальный ID устройства (16 hex-символов)."""
    system = platform.system()
    raw = ""

    try:
        if system == "Windows":
            output = subprocess.check_output(
                "wmic csproduct get uuid", shell=True, stderr=subprocess.DEVNULL
            ).decode().strip()
            raw = output.split('\n')[1].strip()
        elif system == "Darwin":
            output = subprocess.check_output(
                "ioreg -d2 -c IOPlatformExpertDevice | awk -F\\\" '/IOPlatformUUID/{print $(NF-1)}'",
                shell=True, stderr=subprocess.DEVNULL
            ).decode().strip()
            raw = output
        elif system == "Linux":
            # Android тоже Linux — проверяем getprop
            try:
                raw = subprocess.check_output(
                    "getprop ro.serialno", shell=True, stderr=subprocess.DEVNULL
                ).decode().strip()
            except Exception:
                pass
            if not raw:
                try:
                    raw = open("/var/lib/dbus/machine-id").read().strip()
                except Exception:
                    pass
    except Exception:
        pass

    if not raw:
        raw = f"fallback-{platform.node()}-{platform.machine()}"

    return hashlib.sha256(raw.encode()).hexdigest()[:16].upper()


# ─── Валидация ключа (HMAC) ────────────────────────────────────

def validate_key(key_str: str) -> tuple:
    """
    Проверяет HMAC-подпись ключа с привязкой к device_id текущего устройства.
    Ключ валиден ТОЛЬКО на том устройстве, для которого был сгенерирован.
    Возвращает (True, data_dict) или (False, error_message).
    """
    clean = key_str.replace('-', '').replace(' ', '').upper()
    if len(clean) != 20:
        return False, "Неверный формат ключа"

    padded = clean + '=' * ((8 - len(clean) % 8) % 8)
    try:
        raw = base64.b32decode(padded)
    except Exception:
        return False, "Неверные символы в ключе"

    if len(raw) != 12:
        return False, "Неверный формат ключа"

    payload, sig = raw[:4], raw[4:]
    secret = _get_secret()
    device_id = get_device_id()
    # HMAC проверяет payload + device_id → ключ привязан к конкретному устройству
    hmac_data = payload + device_id.encode()
    expected = hmac.new(secret, hmac_data, hashlib.sha256).digest()[:8]

    if not hmac.compare_digest(sig, expected):
        return False, "Ключ не подходит для этого устройства"

    val = struct.unpack('>I', payload)[0]
    data = {
        'subject_idx': (val >> 28) & 0xF,
        'subject': SUBJECTS_REV.get((val >> 28) & 0xF, 'unknown'),
        'client_id': (val >> 12) & 0xFFFF,
        'duration_months': (val >> 4) & 0xFF,
        'flags': val & 0xF,
    }
    return True, data


# ─── Шифрование license.dat ────────────────────────────────────
# Используем HMAC-based keystream XOR + integrity HMAC.
# Ключ шифрования привязан к device_id → нельзя скопировать файл.

_ENC_SALT = b"interactive-posters-license-v2"

def _derive_enc_key(device_id: str) -> bytes:
    """Ключ шифрования, привязанный к устройству."""
    return hashlib.pbkdf2_hmac('sha256', device_id.encode(), _ENC_SALT, 100_000)


def _encrypt_license(data: dict, device_id: str) -> bytes:
    """Шифрует JSON-данные лицензии."""
    key = _derive_enc_key(device_id)
    plaintext = json.dumps(data, ensure_ascii=False).encode('utf-8')

    # Генерируем keystream через HMAC-SHA256 в режиме CTR
    ciphertext = bytearray(len(plaintext))
    for i in range(0, len(plaintext), 32):
        block_key = hmac.new(key, struct.pack('>I', i // 32), hashlib.sha256).digest()
        chunk = plaintext[i:i+32]
        for j, b in enumerate(chunk):
            ciphertext[i + j] = b ^ block_key[j]

    # Integrity tag
    tag = hmac.new(key, bytes(ciphertext), hashlib.sha256).digest()[:16]

    return tag + bytes(ciphertext)


def _decrypt_license(raw: bytes, device_id: str) -> dict:
    """Расшифровывает license.dat. Возвращает dict или None."""
    if len(raw) < 17:
        return None

    key = _derive_enc_key(device_id)
    tag, ciphertext = raw[:16], raw[16:]

    # Проверяем integrity
    expected_tag = hmac.new(key, ciphertext, hashlib.sha256).digest()[:16]
    if not hmac.compare_digest(tag, expected_tag):
        return None  # Файл повреждён или скопирован с другого устройства

    # Расшифровываем
    plaintext = bytearray(len(ciphertext))
    for i in range(0, len(ciphertext), 32):
        block_key = hmac.new(key, struct.pack('>I', i // 32), hashlib.sha256).digest()
        chunk = ciphertext[i:i+32]
        for j, b in enumerate(chunk):
            plaintext[i + j] = b ^ block_key[j]

    try:
        return json.loads(bytes(plaintext).decode('utf-8'))
    except Exception:
        return None


# ─── Активация ──────────────────────────────────────────────────

def activate_key(key_str: str) -> tuple:
    """
    Активирует лицензионный ключ.
    Срок действия начинается С МОМЕНТА АКТИВАЦИИ.
    Возвращает (True, message) или (False, error_message).
    """
    valid, result = validate_key(key_str)
    if not valid:
        return False, result

    device_id = get_device_id()
    now = datetime.now()
    duration = result['duration_months']
    expires = now + timedelta(days=duration * 30)

    license_data = {
        'key_hash': hashlib.sha256(key_str.upper().encode()).hexdigest(),
        'device_id': device_id,
        'subject': result['subject'],
        'subject_idx': result['subject_idx'],
        'client_id': result['client_id'],
        'duration_months': duration,
        'activated_at': now.isoformat(timespec='seconds'),
        'expires_at': expires.isoformat(timespec='seconds'),
        'last_check': now.isoformat(timespec='seconds'),
        'version': 2,
    }

    try:
        encrypted = _encrypt_license(license_data, device_id)
        with open(LICENSE_FILE, 'wb') as f:
            f.write(encrypted)
    except Exception as e:
        return False, f"Ошибка сохранения лицензии: {e}"

    months_word = _months_word(duration)
    return True, f"Активация успешна! Лицензия действительна {duration} {months_word}."


# ─── Проверка лицензии ──────────────────────────────────────────

def is_activated() -> bool:
    """Проверяет, активировано ли приложение и не истёк ли срок."""
    status = get_license_status()
    return status['valid']


def get_license_status() -> dict:
    """
    Полная проверка лицензии. Возвращает словарь:
    {
        'valid': bool,
        'reason': str,           # Причина если невалидна
        'subject': str|None,
        'expires_at': str|None,
        'days_left': int|None,
    }
    """
    result = {
        'valid': False,
        'reason': 'Лицензия не найдена',
        'subject': None,
        'expires_at': None,
        'days_left': None,
    }

    if not os.path.exists(LICENSE_FILE):
        return result

    try:
        with open(LICENSE_FILE, 'rb') as f:
            raw = f.read()
    except Exception:
        result['reason'] = 'Ошибка чтения файла лицензии'
        return result

    device_id = get_device_id()
    data = _decrypt_license(raw, device_id)

    if data is None:
        result['reason'] = 'Лицензия повреждена или принадлежит другому устройству'
        return result

    # Проверяем версию формата
    if data.get('version') != 2:
        result['reason'] = 'Устаревший формат лицензии'
        return result

    # Проверяем device_id
    if data.get('device_id') != device_id:
        result['reason'] = 'Лицензия привязана к другому устройству'
        return result

    now = datetime.now()

    # ─── Защита от перевода часов назад ───
    try:
        last_check = datetime.fromisoformat(data['last_check'])
        drift = last_check - now
        if drift.total_seconds() > _MAX_CLOCK_DRIFT_HOURS * 3600:
            result['reason'] = 'Обнаружено изменение системных часов. Обратитесь в поддержку.'
            return result
    except Exception:
        pass

    # ─── Проверяем срок действия ───
    try:
        expires_at = datetime.fromisoformat(data['expires_at'])
    except Exception:
        result['reason'] = 'Повреждены данные лицензии'
        return result

    if now > expires_at:
        result['reason'] = 'Срок действия лицензии истёк'
        result['expires_at'] = data['expires_at']
        return result

    days_left = (expires_at - now).days

    # ─── Обновляем last_check ───
    try:
        data['last_check'] = now.isoformat(timespec='seconds')
        encrypted = _encrypt_license(data, device_id)
        with open(LICENSE_FILE, 'wb') as f:
            f.write(encrypted)
    except Exception:
        pass  # Не критично — работаем дальше

    result['valid'] = True
    result['reason'] = 'OK'
    result['subject'] = data.get('subject')
    result['expires_at'] = data['expires_at']
    result['days_left'] = days_left

    return result


def get_activated_subject() -> str:
    """Возвращает код активированного предмета или None."""
    status = get_license_status()
    if status['valid']:
        return status['subject']
    return None


# ─── Утилиты ────────────────────────────────────────────────────

def _months_word(n: int) -> str:
    """Склонение слова 'месяц'."""
    if 11 <= n % 100 <= 19:
        return "месяцев"
    r = n % 10
    if r == 1:
        return "месяц"
    if 2 <= r <= 4:
        return "месяца"
    return "месяцев"
