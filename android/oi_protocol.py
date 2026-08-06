# -*- coding: utf-8 -*-
"""
Сборочная криптография «Интерактивных плакатов» v4 (само­достаточная).

Шифрует контент предметов при синхронизации в assets и выводит ключ контента из
мастер-ключа экосистемы. Формат шифрования (OLENC2, AES-256-GCM) и вывод ключа
контента ИДЕНТИЧНЫ product_core._protocol — иначе расшифровка в приложении
(Licensing.kt) не совпадёт.

Мастер-ключ берётся из ecosystem.keys (НЕ в репозитории — см. sync_content.py).
Приватный ключ подписи здесь НЕ используется: лицензии подписывает только бот,
в сборку попадает лишь публичный ключ проверки (product_config.json).
"""
import hashlib
import hmac
import os

CONTENT_MAGIC2 = b"OLENC2\n"   # AES-256-GCM (как в product_core._protocol)


def derive_content_key(content_master: bytes, product_id: int, variant_id: int = 0) -> bytes:
    """variant_id=0 → b"content:"+product_id (совместимость); variant>0 → отдельный
    ключ на предмет (ключ одного предмета не открывает другой)."""
    msg = b"content:" + bytes([product_id & 0xFF])
    if variant_id:
        msg += b":" + bytes([variant_id & 0xFF])
    return hmac.new(content_master, msg, hashlib.sha256).digest()


def encrypt_content(data: bytes, content_key: bytes) -> bytes:
    """OLENC2\\n + nonce(12) + AES-256-GCM(ct+tag). Совпадает с Kotlin decryptContent()."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return CONTENT_MAGIC2 + nonce + AESGCM(content_key).encrypt(nonce, data, None)


def is_encrypted(raw: bytes) -> bool:
    return raw[:len(CONTENT_MAGIC2)] == CONTENT_MAGIC2
