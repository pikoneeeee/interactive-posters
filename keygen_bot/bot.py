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
    /verify     — Проверить ключ
    /list       — Список выданных ключей (последние 20)
    /listall    — Все ключи
    /revoke     — Отозвать ключ (удалить из БД)
"""

import asyncio
import os
import sys

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
)
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from dotenv import load_dotenv

# Добавляем родительскую папку в path для импорта keygen
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keygen

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
    client_id = State()
    months = State()
    note = State()


class VerifyKey(StatesGroup):
    key = State()


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
        "/gen — Сгенерировать ключ\n"
        "/verify — Проверить ключ\n"
        "/list — Последние 20 ключей\n"
        "/listall — Все ключи\n"
        "/revoke — Удалить ключ из БД\n"
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
        "*Генерация ключа (/gen):*\n"
        "1. Выберите предмет\n"
        "2. Введите ID клиента (0–65535)\n"
        "3. Выберите срок (месяцы)\n"
        "4. Добавьте заметку (опционально)\n\n"
        f"*Доступные предметы:*\n`{subjects_list}`\n\n"
        "*Проверка (/verify):*\n"
        "Отправьте ключ в формате XXXX-XXXX-XXXX-XXXX-XXXX\n\n"
        "*Формат ключа:*\n"
        "• Привязан к предмету и клиенту\n"
        "• Срок действия начинается с момента активации\n"
        "• Привязывается к устройству при активации",
        parse_mode="Markdown"
    )


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
        "👤 *Шаг 2/4:* Введите ID клиента (число 0–65535):",
        parse_mode="Markdown"
    )
    await state.set_state(GenKey.client_id)
    await callback.answer()


# ─── Шаг 2: client_id ─────────────────────────────────────────
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
        "📅 *Шаг 3/4:* Выберите срок действия:",
        reply_markup=kb, parse_mode="Markdown"
    )
    await state.set_state(GenKey.months)


# ─── Шаг 3: duration ──────────────────────────────────────────
@router.callback_query(F.data.startswith("dur_"), GenKey.months)
async def gen_months_chosen(callback: CallbackQuery, state: FSMContext):
    months = int(callback.data.replace("dur_", ""))
    await state.update_data(months=months)
    await callback.message.edit_text(
        f"📅 Срок: *{months} мес.*\n\n"
        "📝 *Шаг 4/4:* Введите заметку (название школы/клиента)\n"
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
    client_id = data['client_id']
    months = data['months']

    try:
        secret = keygen.load_secret()
        key_str = keygen.encode_key(keygen.SUBJECTS[subject], client_id, months, 0, secret)

        # Сохранение в БД
        conn = keygen._init_db()
        keygen._save_key(conn, key_str, subject, client_id, months, 0, note)
        conn.close()

        result = (
            "✅ *Ключ сгенерирован!*\n\n"
            f"```\n{key_str}\n```\n\n"
            f"📚 Предмет: `{subject}`\n"
            f"👤 Клиент: `#{client_id}`\n"
            f"📅 Срок: `{months} мес.` (с момента активации)\n"
        )
        if note:
            result += f"📝 Заметка: _{note}_\n"

        await message.answer(result, parse_mode="Markdown")

    except Exception as e:
        await message.answer(f"❌ Ошибка генерации: `{e}`", parse_mode="Markdown")


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
async def verify_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    key_str = message.text.strip().upper()
    await state.clear()

    try:
        secret = keygen.load_secret()
        data, err = keygen.decode_key(key_str, secret)

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


# ─── Запуск ───────────────────────────────────────────────────
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    print("🤖 Бот запущен!")
    print(f"   Администраторы: {ADMIN_IDS}")
    print(f"   Нажмите Ctrl+C для остановки")

    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
