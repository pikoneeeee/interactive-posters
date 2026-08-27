# -*- coding: utf-8 -*-
"""
Telegram-бот для генерации лицензионных ключей «Интерактивных плакатов».

Запуск:
    1. Скопируйте .env.example → .env и заполните BOT_TOKEN + ADMIN_IDS
    2. pip install -r requirements.txt
    3. python bot.py

Команды:
    /start      — Приветствие
    /help       — Список команд
    /gen        — Сгенерировать ключ (интерактивно)
    /genqr      — QR-лицензия v4 (все продукты на новом ядре)
    /cancel     — Отменить текущий диалог
    /verify     — Проверить ключ
    /list       — Список выданных ключей v2 (последние 20)
    /listall    — Все ключи v2
    /pclist     — Список выданных QR-лицензий v4 (последние 20)
    /pclistall  — Все QR-лицензии v4
    /revoke     — Отозвать ключ v2 (удалить из БД)
"""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery, ErrorEvent,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    BufferedInputFile,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.session.aiohttp import AiohttpSession
from dotenv import load_dotenv

# Добавляем родительскую папку в path для импорта keygen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keygen

# ─── product-core v4: QR-лицензии для новых продуктов ───
import base64
import io
import json
from datetime import datetime
import pc_protocol as pcp

PC_KEYSTORE = os.getenv("PC_KEYSTORE",
                        os.path.join(os.path.dirname(os.path.abspath(__file__)), "pc_ecosystem.keys"))

PC_PRODUCTS = {
    # Интерактивные плакаты — поштучная продажа предметов: variant = предмет,
    # variant 0 = «Все предметы» (сборка allsubjects). Список ДОЛЖЕН совпадать с
    # SUBJECT_VARIANTS в android/sync_content.py и VARIANT_ID во build.gradle.kts.
    "interactive-posters": {"id": 1, "name": "Интерактивные плакаты", "variants": {
        0: "Все предметы", 1: "Физика", 2: "Математика", 3: "Биология", 4: "Химия",
        5: "География", 6: "Информатика",
        12: "История (Казахстана + Всемирная)",
        9: "Қазақ тілі", 10: "Русский язык", 11: "Английский язык",
    }},
    "interactive-map":    {"id": 4, "name": "Historic Map",       "variant": 0},
    "smart-dictionary":   {"id": 2, "name": "Smart Dictionary",       "variant": 0},
    "math-tools":         {"id": 5, "name": "Interactive Math",    "variant": 0},
    "music-encyclopedia": {"id": 6, "name": "Music Vision",        "variant": 0},
    "speech-therapy":     {"id": 7, "name": "Logo Games",          "variant": 0},
    "3d-models":          {"id": 3, "name": "3D Models",           "variant": 0},
    "virtual-stands": {"id": 9, "name": "Virtual Stands", "variants": {
        0: "Все предметы", 1: "Биология", 2: "Химия", 3: "Физика",
    }},
}

def _pc_license(product_id, variant_id, client_id, months, device_id):
    ks = json.loads(open(PC_KEYSTORE, encoding="utf-8").read())
    priv = bytes.fromhex(ks["ed25519_priv"])
    content_key = pcp.derive_content_key(bytes.fromhex(ks["content_master"]), product_id, variant_id)
    payload = pcp.pack_payload(product_id, variant_id, client_id, months)
    sig = pcp.sign_license(priv, payload, content_key, device_id)
    return pcp.encode_license(payload, content_key, sig)

# ─── LEGACY-20: короткий ключ для сборок со старым ядром ───────────
# Запасная схема: ключ XXXX-XXXX-XXXX-XXXX-XXXX вводится руками, QR не нужен.
# Секрет выводится из мастер-ключа той же формулой, что и при сборке
# (product-core-legacy20/build/android.py -> _legacy_secret), поэтому ключи
# подходят к APK из ветки legacy-20char.
#
# Плакаты (id 1) — исключение: у них своя старая схема со своим secrets.key,
# ключи для них выдаёт keygen.py (как и раньше в /gen).
import hashlib
import hmac as _hmac
import struct

# Предмет плакатов -> индекс в старом ключе (keygen.SUBJECTS)
POSTER_SUBJECT_BY_VARIANT = {
    0: "allsubjects", 1: "physics", 2: "mathematics", 3: "biology", 4: "chemistry",
    5: "geography", 6: "informatics", 7: "historykaz", 8: "worldhistory",
    9: "kazakhlang", 10: "russianlang", 11: "englishlang",
}


def _legacy20_secret(product_id: int) -> bytes:
    ks = json.loads(open(PC_KEYSTORE, encoding="utf-8").read())
    master = bytes.fromhex(ks["content_master"])
    return _hmac.new(master, f"legacy20:{product_id}".encode(), hashlib.sha256).digest()


def _legacy20_key(product_id: int, variant_id: int, client_id: int,
                  months: int, device_id: str) -> str:
    """Короткий ключ для продуктов на ядре legacy-20char."""
    secret = _legacy20_secret(product_id)
    val = ((variant_id & 0xF) << 28) | ((client_id & 0xFFFF) << 12) | \
          ((months & 0xFF) << 4)
    payload = struct.pack(">I", val)
    sig = _hmac.new(secret, payload + device_id.upper().encode(), hashlib.sha256).digest()[:8]
    enc = base64.b32encode(payload + sig).decode().rstrip("=")
    return "-".join(enc[i:i + 4] for i in range(0, 20, 4))


def _legacy_key_for(pc_slug: str, product_id: int, variant_id: int,
                    client_id: int, months: int, device_id: str) -> str:
    """Плакаты — своим старым генератором, остальные — схемой legacy20."""
    if pc_slug == "interactive-posters":
        subject = POSTER_SUBJECT_BY_VARIANT.get(variant_id)
        if subject is None:
            raise ValueError(
                f"для варианта {variant_id} короткого ключа не существует: "
                "объединённая сборка «История» есть только в новой версии — "
                "выдайте QR-лицензию вместо ключа 20 символов")
        secret = keygen.load_secret()
        return keygen.encode_key(keygen.SUBJECTS[subject], client_id, months, 0,
                                 secret, device_id)
    return _legacy20_key(product_id, variant_id, client_id, months, device_id)


def _get_or_create_pc_client_id(name: str) -> int:
    """ID клиента по названию школы: если школа уже встречалась — тот же ID, иначе новый."""
    conn = keygen._init_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pc_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    norm = name.strip().lower()
    for row_id, row_name in conn.execute("SELECT id, name FROM pc_clients"):
        if row_name.strip().lower() == norm:
            conn.close()
            return row_id
    cur = conn.execute(
        "INSERT INTO pc_clients (name, created_at) VALUES (?, ?)",
        (name, datetime.utcnow().isoformat())
    )
    conn.commit()
    cid = cur.lastrowid
    conn.close()
    return cid


def _save_pc_license(product_slug, product_id, variant_id, client_id, client_name, device_id, months, issued_by):
    """Записывает выданную QR-лицензию (v4) в базу — для /pclist и /pclistall."""
    conn = keygen._init_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pc_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_slug TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            device_id TEXT NOT NULL,
            months INTEGER NOT NULL,
            issued_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute(
        "INSERT INTO pc_licenses (product_slug, product_id, variant_id, client_id, client_name, "
        "device_id, months, issued_by, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (product_slug, product_id, variant_id, client_id, client_name, device_id, months, issued_by,
         datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()


async def _show_pc_licenses(message: Message, limit=None):
    conn = keygen._init_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS pc_licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_slug TEXT NOT NULL,
            product_id INTEGER NOT NULL,
            variant_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            client_name TEXT NOT NULL,
            device_id TEXT NOT NULL,
            months INTEGER NOT NULL,
            issued_by INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    query = ("SELECT product_slug, variant_id, client_name, device_id, months, created_at "
             "FROM pc_licenses ORDER BY id DESC")
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM pc_licenses").fetchone()[0]
    conn.close()

    if not rows:
        await message.answer("📋 QR-лицензий пока нет.")
        return

    lines = [f"📋 *QR-лицензии* (показано {len(rows)} из {total}):\n"]
    for i, (slug, vid, cname, did, months, created) in enumerate(rows, 1):
        prod = PC_PRODUCTS.get(slug, {})
        vlabel = f" — {prod['variants'].get(vid, vid)}" if prod.get("variants") else ""
        lines.append(
            f"`{i}.` {prod.get('name', slug)}{vlabel}\n"
            f"    {cname} | `{did}` | {months}мес | {created[:10]}\n"
        )

    text = '\n'.join(lines)
    if len(text) > 4000:
        parts, current = [], ""
        for line in lines:
            if len(current) + len(line) > 3900:
                parts.append(current)
                current = line
            else:
                current += '\n' + line
        if current:
            parts.append(current)
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


def _qr_png(text):
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=14, border=4)
    qr.add_data(text)
    qr.make(fit=True)
    buf = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buf, format="PNG")
    return buf.getvalue()

# ─── Конфигурация ─────────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

BOT_TOKEN = os.getenv('BOT_TOKEN', '')
ADMIN_IDS = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]

if not BOT_TOKEN:
    print("❌ BOT_TOKEN не задан в .env файле!")
    sys.exit(1)

if not ADMIN_IDS:
    print("❌ ADMIN_IDS не задан в .env файле!")
    sys.exit(1)


# ─── Состояния FSM ────────────────────────────────────────────
class GenKey(StatesGroup):
    subject = State()
    device_id = State()
    client_id = State()
    months = State()
    note = State()


class VerifyKey(StatesGroup):
    key = State()
    device_id = State()


class RevokeKey(StatesGroup):
    key = State()


# ─── Роутер ───────────────────────────────────────────────────
router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── /start ───────────────────────────────────────────────────
@router.message(CommandStart())
async def cmd_start(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer(
        "🔐 *Keygen Bot — Интерактивные плакаты*\n\n"
        "Команды:\n"
        "/gen — Ключ v2 для плакат (устаревший формат)\n"
        "/genqr — QR-лицензия v4 (все продукты на новом ядре)\n"
        "/cancel — Отменить текущий диалог\n"
        "/verify — Проверить ключ v2\n"
        "/list — Последние 20 ключей v2\n"
        "/listall — Все ключи v2\n"
        "/pclist — Последние 20 QR-лицензий v4\n"
        "/pclistall — Все QR-лицензии v4\n"
        "/revoke — Удалить ключ v2 из БД\n"
        "/help — Справка",
        parse_mode="Markdown"
    )


# ─── /help ────────────────────────────────────────────────────
@router.message(Command("help"))
async def cmd_help(message: Message):
    if not is_admin(message.from_user.id):
        return
    subjects_list = ', '.join(sorted(keygen.SUBJECTS.keys()))
    await message.answer(
        "📋 *Справка*\n\n"
        "*QR-лицензия v4 (/genqr) — для всех продуктов на новом ядре:*\n"
        "1. Выберите продукт (и предмет, если продукт многопредметный)\n"
        "2. Введите Device ID\n"
        "3. Введите название школы/клиента (ID подбирается сам)\n"
        "4. Выберите срок — бот пришлёт QR-код + строку лицензии\n"
        "Выданные QR-лицензии видны в /pclist и /pclistall.\n\n"
        "*Отмена (/cancel):* сбрасывает текущий диалог на любом шаге.\n\n"
        "*Генерация ключа v2 (/gen) — устаревший формат, только плакаты:*\n"
        "1. Выберите предмет\n"
        "2. Введите ID клиента (0–65535)\n"
        "3. Выберите срок (месяцы)\n"
        "4. Добавьте заметку (опционально)\n\n"
        f"*Доступные предметы (v2):*\n`{subjects_list}`\n\n"
        "*Проверка (/verify):*\n"
        "Отправьте ключ в формате XXXX-XXXX-XXXX-XXXX-XXXX (только для ключей v2)\n\n"
        "*Формат ключа v2:*\n"
        "• Привязан к предмету и клиенту\n"
        "• Срок действия начинается с момента активации\n"
        "• Привязывается к устройству при активации",
        parse_mode="Markdown"
    )


# ─── /cancel — Отмена текущего диалога (работает на любом шаге) ─
@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    current = await state.get_state()
    await state.clear()
    if current is None:
        await message.answer("Нечего отменять.")
    else:
        await message.answer("❌ Отменено.")


# ─── /gen — Генерация ключа (шаг 1: предмет) ─────────────────
@router.message(Command("gen"))
async def cmd_gen_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    # Кнопки предметов
    subjects = sorted(keygen.SUBJECTS.keys())
    buttons = []
    row = []
    for s in subjects:
        row.append(InlineKeyboardButton(text=s, callback_data=f"subj_{s}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("📚 *Шаг 1/4:* Выберите предмет:", reply_markup=kb, parse_mode="Markdown")
    await state.set_state(GenKey.subject)


@router.callback_query(F.data.startswith("subj_"), GenKey.subject)
async def gen_subject_chosen(callback: CallbackQuery, state: FSMContext):
    subject = callback.data.replace("subj_", "")
    await state.update_data(subject=subject)
    await callback.message.edit_text(
        f"📚 Предмет: *{subject}*\n\n"
        "� *Шаг 2/5:* Введите Device ID устройства (16 символов):\n"
        "Пользователь видит его на экране активации.",
        parse_mode="Markdown"
    )
    await state.set_state(GenKey.device_id)
    await callback.answer()


# ─── Шаг 2: device_id ─────────────────────────────────────
@router.message(GenKey.device_id)
async def gen_device_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    did = message.text.strip().upper()
    if len(did) != 16:
        await message.answer("❌ Device ID должен быть ровно 16 символов. Попробуйте ещё:")
        return

    await state.update_data(device_id=did)
    await message.answer(
        f"💻 Устройство: `{did}`\n\n"
        "👤 *Шаг 3/5:* Введите ID клиента (число 0–65535):",
        parse_mode="Markdown"
    )
    await state.set_state(GenKey.client_id)


# ─── Шаг 3: client_id ─────────────────────────────────────
@router.message(GenKey.client_id)
async def gen_client_id(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        cid = int(message.text.strip())
        if not (0 <= cid <= 65535):
            raise ValueError
    except ValueError:
        await message.answer("❌ Введите число от 0 до 65535:")
        return

    await state.update_data(client_id=cid)

    # Кнопки сроков
    buttons = [
        [
            InlineKeyboardButton(text="3 мес", callback_data="dur_3"),
            InlineKeyboardButton(text="6 мес", callback_data="dur_6"),
            InlineKeyboardButton(text="12 мес", callback_data="dur_12"),
        ],
        [
            InlineKeyboardButton(text="18 мес", callback_data="dur_18"),
            InlineKeyboardButton(text="24 мес", callback_data="dur_24"),
            InlineKeyboardButton(text="36 мес", callback_data="dur_36"),
        ],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(
        f"👤 Клиент: *#{cid}*\n\n"
        "📅 *Шаг 4/5:* Выберите срок действия:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await state.set_state(GenKey.months)


# ─── Шаг 4: duration ──────────────────────────────────────────
@router.callback_query(F.data.startswith("dur_"), GenKey.months)
async def gen_months_chosen(callback: CallbackQuery, state: FSMContext):
    months = int(callback.data.replace("dur_", ""))
    await state.update_data(months=months)
    await callback.message.edit_text(
        f"📅 Срок: *{months} мес.*\n\n"
        "📝 *Шаг 5/5:* Введите заметку (название школы/клиента)\n"
        "или отправьте `-` чтобы пропустить:",
        parse_mode="Markdown"
    )
    await state.set_state(GenKey.note)
    await callback.answer()


# ─── Шаг 4: note → генерация ──────────────────────────────────
@router.message(GenKey.note)
async def gen_note_and_create(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    note = message.text.strip()
    if note == '-':
        note = ''
    await state.update_data(note=note)

    data = await state.get_data()
    await state.clear()

    # Генерация ключа
    subject = data['subject']
    device_id = data['device_id']
    client_id = data['client_id']
    months = data['months']

    try:
        secret = keygen.load_secret()
        key_str = keygen.encode_key(keygen.SUBJECTS[subject], client_id, months, 0, secret, device_id)

        # Сохранение в БД
        conn = keygen._init_db()
        keygen._save_key(conn, key_str, subject, client_id, months, 0, device_id, note)
        conn.close()

        result = (
            "✅ *Ключ сгенерирован!*\n\n"
            f"```\n{key_str}\n```\n\n"
            f"📚 Предмет: `{subject}`\n"
            f"💻 Устройство: `{device_id}`\n"
            f"👤 Клиент: `#{client_id}`\n"
            f"📅 Срок: `{months} мес.` (с момента активации)\n"
            f"⚠️ Привязан к устройству — не работает на других ПК\n"
        )
        if note:
            result += f"📝 Заметка: _{note}_\n"

        await message.answer(result, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка генерации: `{e}`", parse_mode="Markdown")


# ─── /genqr — QR-лицензия v4 (новые продукты на ядре) ──────────
class PcGen(StatesGroup):
    product = State()
    variant = State()
    device_id = State()
    client_id = State()
    months = State()


@router.message(Command("genqr"))
async def cmd_genqr(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await state.update_data(legacy=False)
    rows = [[InlineKeyboardButton(text=v["name"], callback_data=f"pcp_{k}")]
            for k, v in PC_PRODUCTS.items()]
    # Отдельной кнопкой — тот же ход, но короткий ключ для сборок со старым ядром
    rows.append([InlineKeyboardButton(text="(не желательно) Старые версии (ключ 20 символов)",
                                      callback_data="pcold")])
    await message.answer("🆕 *QR-лицензия (v4)*\n\nШаг 1/4: выберите продукт:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await state.set_state(PcGen.product)


@router.callback_query(F.data == "pcold", PcGen.product)
async def pcgen_legacy(callback: CallbackQuery, state: FSMContext):
    """Переключает тот же диалог в режим короткого ключа (сборки без QR)."""
    await state.update_data(legacy=True)
    rows = [[InlineKeyboardButton(text=v["name"], callback_data=f"pcp_{k}")]
            for k, v in PC_PRODUCTS.items()]
    await callback.message.edit_text(
        "🔑 *Ключ 20 символов (старые сборки)*\n\n"
        "Для APK, где активация вводится руками и QR нет.\n\n"
        "Шаг 1/4: выберите продукт:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await callback.answer()


@router.callback_query(F.data.startswith("pcp_"), PcGen.product)
async def pcgen_product(callback: CallbackQuery, state: FSMContext):
    try:
        key = callback.data.replace("pcp_", "")
        await state.update_data(pc=key)
        prod = PC_PRODUCTS[key]
        variants = prod.get("variants")
        if variants:
            # Многовариантный продукт (плакаты): выбираем предмет/«Все предметы»
            rows, row = [], []
            for vid, vname in variants.items():
                row.append(InlineKeyboardButton(text=vname, callback_data=f"pcv_{vid}"))
                if len(row) == 2:
                    rows.append(row); row = []
            if row:
                rows.append(row)
            await callback.message.edit_text(
                f"Продукт: *{prod['name']}*\n\nШаг 2: выберите предмет (вариант лицензии):",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
            await state.set_state(PcGen.variant)
        else:
            await callback.message.edit_text(
                f"Продукт: *{prod['name']}*\n\n"
                "Введите *Device ID* (16 hex с экрана активации доски):",
                parse_mode="Markdown")
            await state.set_state(PcGen.device_id)
    except Exception as e:
        await state.clear()
        await callback.message.answer(f"❌ Ошибка: {e}\nНачните заново: /genqr")
    await callback.answer()


@router.callback_query(F.data.startswith("pcv_"), PcGen.variant)
async def pcgen_variant(callback: CallbackQuery, state: FSMContext):
    try:
        vid = int(callback.data.replace("pcv_", ""))
        await state.update_data(variant=vid)
        data = await state.get_data()
        prod = PC_PRODUCTS[data["pc"]]
        vname = prod["variants"].get(vid, str(vid))
        await callback.message.edit_text(
            f"Продукт: *{prod['name']}* — *{vname}*\n\n"
            "Введите *Device ID* (16 hex с экрана активации доски):",
            parse_mode="Markdown")
        await state.set_state(PcGen.device_id)
    except Exception as e:
        await state.clear()
        await callback.message.answer(f"❌ Ошибка: {e}\nНачните заново: /genqr")
    await callback.answer()


@router.message(PcGen.device_id)
async def pcgen_device(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        did = message.text.strip().upper()
        if len(did) != 16:
            await message.answer("❌ Device ID должен быть ровно 16 символов. Ещё раз:")
            return
        await state.update_data(device_id=did)
        await message.answer(f"💻 Устройство: `{did}`\n\nШаг 3/4: название школы/клиента:", parse_mode="Markdown")
        await state.set_state(PcGen.client_id)
    except Exception as e:
        await state.clear()
        await message.answer(f"❌ Ошибка: {e}\nНачните заново: /genqr")


@router.message(PcGen.client_id)
async def pcgen_client(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if not name:
        await message.answer("❌ Введите название школы/клиента:")
        return
    cid = _get_or_create_pc_client_id(name)
    await state.update_data(client_id=cid, client_name=name)
    rows = [
        [InlineKeyboardButton(text="3 мес", callback_data="pcd_3"),
         InlineKeyboardButton(text="6 мес", callback_data="pcd_6"),
         InlineKeyboardButton(text="12 мес", callback_data="pcd_12")],
        [InlineKeyboardButton(text="24 мес", callback_data="pcd_24"),
         InlineKeyboardButton(text="36 мес", callback_data="pcd_36"),
         InlineKeyboardButton(text="60 мес", callback_data="pcd_60")],
    ]
    await message.answer(f"👤 Клиент: *{name}* (#{cid})\n\nШаг 4/4: срок действия:",
                         reply_markup=InlineKeyboardMarkup(inline_keyboard=rows), parse_mode="Markdown")
    await state.set_state(PcGen.months)


@router.callback_query(F.data.startswith("pcd_"), PcGen.months)
async def pcgen_months(callback: CallbackQuery, state: FSMContext):
    months = int(callback.data.replace("pcd_", ""))
    data = await state.get_data()
    await state.clear()
    prod = PC_PRODUCTS[data["pc"]]
    did = data["device_id"]
    cid = data["client_id"]
    cname = data.get("client_name", f"#{cid}")
    variant = data.get("variant", prod.get("variant", 0))
    vlabel = f" — {prod['variants'].get(variant, variant)}" if prod.get("variants") else ""
    legacy = data.get("legacy", False)
    try:
        if legacy:
            # Старые сборки: короткий ключ, вводится руками, QR не нужен
            key = _legacy_key_for(data["pc"], prod["id"], variant, cid, months, did)
            await callback.message.answer(
                f"🔑 *Ключ 20 символов готов*\n\n"
                f"Продукт: {prod['name']}{vlabel} (id {prod['id']})\n"
                f"Устройство: `{did}`\n"
                f"Клиент: {cname} (#{cid})   Срок: {months} мес.\n\n"
                "На доске: введите ключ на экране активации.\n"
                "_Только для сборок со старым ядром (без QR)._",
                parse_mode="Markdown")
            await callback.message.answer(f"`{key}`", parse_mode="Markdown")
        else:
            lic = _pc_license(prod["id"], variant, cid, months, did)
            png = _qr_png(lic)
            caption = (
                f"✅ QR-лицензия готова\n\n"
                f"Продукт: {prod['name']}{vlabel} (id {prod['id']})\n"
                f"Устройство: {did}\n"
                f"Клиент: {cname} (#{cid})   Срок: {months} мес.\n\n"
                "На доске: «📷 Сканировать QR-код» → наведите камеру на этот QR."
            )
            await callback.message.answer_photo(
                BufferedInputFile(png, filename=f"license_{did}.png"), caption=caption)
            await callback.message.answer(lic)

        _save_pc_license(data["pc"], prod["id"], variant, cid, cname, did, months, callback.from_user.id)
    except FileNotFoundError:
        await callback.message.answer("❌ Не найден ключ подписи (PC_KEYSTORE / pc_ecosystem.keys рядом с ботом).")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")
    await callback.answer()


# ─── /pclist, /pclistall — Выданные QR-лицензии (v4) ───────────
@router.message(Command("pclist"))
async def cmd_pclist(message: Message):
    if not is_admin(message.from_user.id):
        return
    await _show_pc_licenses(message, limit=20)


@router.message(Command("pclistall"))
async def cmd_pclistall(message: Message):
    if not is_admin(message.from_user.id):
        return
    await _show_pc_licenses(message, limit=None)


# ─── /verify — Проверить ключ ──────────────────────────────────
@router.message(Command("verify"))
async def cmd_verify_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🔍 Отправьте ключ для проверки\n"
        "(формат: `XXXX-XXXX-XXXX-XXXX-XXXX`):",
        parse_mode="Markdown"
    )
    await state.set_state(VerifyKey.key)


@router.message(VerifyKey.key)
async def verify_key_received(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key_str = message.text.strip().upper()
    await state.update_data(key=key_str)
    await message.answer(
        "💻 Введите Device ID устройства (16 символов)\n"
        "для проверки привязки ключа:",
        parse_mode="Markdown"
    )
    await state.set_state(VerifyKey.device_id)


@router.message(VerifyKey.device_id)
async def verify_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    device_id = message.text.strip().upper()
    if len(device_id) != 16:
        await message.answer("❌ Device ID должен быть 16 символов:")
        return

    data_state = await state.get_data()
    key_str = data_state['key']
    await state.clear()

    try:
        secret = keygen.load_secret()
        data, err = keygen.decode_key(key_str, secret, device_id)

        if err:
            await message.answer(f"❌ *Невалидный ключ*\n\n{err}", parse_mode="Markdown")
            return

        # Проверяем в БД
        conn = keygen._init_db()
        row = conn.execute(
            "SELECT note, created_at FROM keys WHERE key_str = ?", (key_str,)
        ).fetchone()
        conn.close()

        result = (
            "✅ *Ключ валидный*\n\n"
            f"📚 Предмет: `{data['subject']}`\n"
            f"💻 Устройство: `{device_id}`\n"
            f"👤 Клиент: `#{data['client_id']}`\n"
            f"📅 Срок: `{data['duration_months']} мес.`\n"
        )
        if row:
            note, created = row
            result += f"📅 Создан: `{created}`\n"
            if note:
                result += f"📝 Заметка: _{note}_\n"
        else:
            result += "\n⚠️ _Ключ НЕ найден в базе (возможно создан через CLI)_"

        await message.answer(result, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка: `{e}`", parse_mode="Markdown")


# ─── /list — Последние 20 ключей ──────────────────────────────
@router.message(Command("list"))
async def cmd_list(message: Message):
    if not is_admin(message.from_user.id):
        return
    await _show_keys(message, limit=20)


@router.message(Command("listall"))
async def cmd_listall(message: Message):
    if not is_admin(message.from_user.id):
        return
    await _show_keys(message, limit=None)


async def _show_keys(message: Message, limit=None):
    conn = keygen._init_db()
    query = "SELECT key_str, subject, client_id, duration_months, note, created_at FROM keys ORDER BY id DESC"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query).fetchall()
    conn.close()

    if not rows:
        await message.answer("📋 Ключей пока нет.")
        return

    total = keygen._init_db().execute("SELECT COUNT(*) FROM keys").fetchone()[0]

    lines = [f"📋 *Ключи* (показано {len(rows)} из {total}):\n"]
    for i, (key_str, subj, cid, dur, note, created) in enumerate(rows, 1):
        note_str = f" — _{note}_" if note else ""
        lines.append(
            f"`{i}.` `{key_str}`\n"
            f"    {subj} | #{cid} | {dur}мес | {created[:10]}{note_str}\n"
        )

    # Telegram ограничивает сообщения в 4096 символов
    text = '\n'.join(lines)
    if len(text) > 4000:
        # Разбиваем на части
        parts = []
        current = ""
        for line in lines:
            if len(current) + len(line) > 3900:
                parts.append(current)
                current = line
            else:
                current += '\n' + line
        if current:
            parts.append(current)
        for part in parts:
            await message.answer(part, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


# ─── /revoke — Удалить ключ из БД ─────────────────────────────
@router.message(Command("revoke"))
async def cmd_revoke_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer(
        "🗑 Отправьте ключ для удаления из БД\n"
        "(формат: `XXXX-XXXX-XXXX-XXXX-XXXX`):\n\n"
        "⚠️ _Это не деактивирует уже активированную лицензию,\n"
        "но ключ больше не будет виден в /list_",
        parse_mode="Markdown"
    )
    await state.set_state(RevokeKey.key)


@router.message(RevokeKey.key)
async def revoke_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key_str = message.text.strip().upper()
    await state.clear()

    conn = keygen._init_db()
    cursor = conn.execute("DELETE FROM keys WHERE key_str = ?", (key_str,))
    deleted = cursor.rowcount
    conn.commit()
    conn.close()

    if deleted:
        await message.answer(f"✅ Ключ `{key_str}` удалён из базы.", parse_mode="Markdown")
    else:
        await message.answer(f"⚠️ Ключ `{key_str}` не найден в базе.", parse_mode="Markdown")


# ─── Обработка неизвестных сообщений от админов ────────────────
@router.message()
async def fallback(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("Используйте /help для списка команд.")


# ─── Глобальный обработчик ошибок ──────────────────────────────
# Ловит исключения из любых хендлеров без собственного try/except,
# чтобы админ видел сообщение об ошибке, а не тишину в чате.
@router.errors()
async def global_error_handler(event: ErrorEvent):
    upd = event.update
    chat_msg = upd.message or (upd.callback_query.message if upd.callback_query else None)
    print(f"⚠️ Необработанная ошибка: {event.exception}")
    if chat_msg:
        try:
            await chat_msg.answer(f"❌ Непредвиденная ошибка: {event.exception}\nСбросить диалог: /cancel")
        except Exception:
            pass
    return True


# ─── Запуск ───────────────────────────────────────────────────
async def main():
    bot = Bot(token=BOT_TOKEN, session=AiohttpSession(timeout=120))
    dp = Dispatcher()
    dp.include_router(router)

    print("🤖 Бот запущен!")
    print(f"   Администраторы: {ADMIN_IDS}")
    print(f"   Нажмите Ctrl+C для остановки")

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
