import os
import httpx
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton

router = Router()
SERVER_URL = "http://127.0.0.1:8000"
MENU_BUTTONS = ["📝 Записка", "👥 Контакты", "⏱ Интервал", "💤 Режим сна", "📊 Статус", "🆘 SOS"]

class Form(StatesGroup):
    waiting_for_note = State()
    waiting_for_interval = State()
    waiting_for_contact = State()
    waiting_for_dnd = State()

def main_menu():
    kb = [
        [KeyboardButton(text="📝 Записка"), KeyboardButton(text="👥 Контакты")],
        [KeyboardButton(text="⏱ Интервал"), KeyboardButton(text="💤 Режим сна")],
        [KeyboardButton(text="📊 Статус"), KeyboardButton(text="🆘 SOS")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

async def check_interruption(message: types.Message, state: FSMContext):
    if message.text in MENU_BUTTONS:
        await state.clear()
        return True
    return False

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/register", json={"telegram_id": message.from_user.id})
    await message.answer("👋 Система мониторинга активна!", reply_markup=main_menu())

@router.message(F.text == "📊 Статус")
async def cmd_status(message: types.Message):
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{SERVER_URL}/status/{message.from_user.id}")
        if resp.status_code == 200:
            d = resp.json()
            contacts_str = "\n".join([f"• {c['info']}" for c in d['contacts']]) if d['contacts'] else "Пусто"
            text = (
                f"📋 **Твой профиль:**\n\n"
                f"⏱ Интервал: {d['check_interval']} ч.\n"
                f"💤 Сон: {d['dnd']}\n"
                f"📝 Записка: {d['death_note']}\n\n"
                f"👥 **Контакты для SOS:**\n{contacts_str}"
            )
            await message.answer(text, parse_mode="Markdown")

@router.message(F.text == "👥 Контакты")
async def contact_menu(message: types.Message, state: FSMContext):
    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Очистить все контакты", callback_data="clear_contacts")]
    ])
    await message.answer("Отправь имя и телефон (напр. Мама +7999...), чтобы добавить в список.\nИли нажми кнопку ниже, чтобы удалить всех:", reply_markup=inline_kb)
    await state.set_state(Form.waiting_for_contact)

@router.callback_query(F.data == "clear_contacts")
async def process_clear_contacts(callback: types.CallbackQuery, state: FSMContext):
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/clear_contacts", json={"telegram_id": callback.from_user.id})
    await callback.message.edit_text("✅ Список контактов очищен.")
    await state.clear()

@router.message(Form.waiting_for_contact)
async def save_contact(message: types.Message, state: FSMContext):
    if await check_interruption(message, state): return await handle_menu_buttons(message, state)
    async with httpx.AsyncClient() as client:
        res = await client.get(f"{SERVER_URL}/status/{message.from_user.id}")
        current_contacts = res.json().get('contacts', [])
        current_contacts.append({"info": message.text})
        await client.post(f"{SERVER_URL}/update_settings", json={"telegram_id": message.from_user.id, "contacts": current_contacts})
    await message.answer(f"✅ Контакт добавлен!", reply_markup=main_menu())
    await state.clear()

@router.message(F.text == "📝 Записка")
async def edit_note(message: types.Message, state: FSMContext):
    res = await httpx.AsyncClient().get(f"{SERVER_URL}/status/{message.from_user.id}")
    current = res.json().get('death_note')
    await message.answer(f"Текущая записка: {current}\n\nВведите новый текст:")
    await state.set_state(Form.waiting_for_note)

@router.message(F.text == "💤 Режим сна")
async def set_dnd(message: types.Message, state: FSMContext):
    res = await httpx.AsyncClient().get(f"{SERVER_URL}/status/{message.from_user.id}")
    current = res.json().get('dnd')
    await message.answer(f"Текущий режим сна: {current}\n\nВведите новый (ЧЧ:ММ-ЧЧ:ММ):")
    await state.set_state(Form.waiting_for_dnd)
    
@router.message(Form.waiting_for_note)
async def save_note(message: types.Message, state: FSMContext):
    if await check_interruption(message, state): return await handle_menu_buttons(message, state)
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/update_settings", json={"telegram_id": message.from_user.id, "death_note": message.text})
    await message.answer("✅ Сохранено!", reply_markup=main_menu()); await state.clear()

@router.message(Form.waiting_for_interval)
async def save_interval(message: types.Message, state: FSMContext):
    if await check_interruption(message, state): return await handle_menu_buttons(message, state)
    try:
        val = float(message.text.replace(",", "."))
        if val <= 0: raise ValueError
    except ValueError:
        return await message.answer("❌ Ошибка! Введите число.")
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/update_settings", json={"telegram_id": message.from_user.id, "check_interval": val})
    await message.answer(f"✅ Интервал обновлен: {val} ч.", reply_markup=main_menu())
    await state.clear()

@router.message(Form.waiting_for_dnd)
async def save_dnd(message: types.Message, state: FSMContext):
    if await check_interruption(message, state): return await handle_menu_buttons(message, state)
    try:
        start, end = message.text.split("-")
        async with httpx.AsyncClient() as client:
            await client.post(f"{SERVER_URL}/update_settings", json={"telegram_id": message.from_user.id, "dnd_start": start, "dnd_end": end})
        await message.answer(f"✅ Сон установлен!", reply_markup=main_menu()); await state.clear()
    except: await message.answer("Ошибка формата!")

@router.message(F.text == "🆘 SOS")
async def manual_sos(message: types.Message):
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/sos_manual", json={"telegram_id": message.from_user.id})
    await message.answer("🚨 SOS АКТИВИРОВАН!")

@router.message(F.text == "⏱ Интервал")
async def set_interval(message: types.Message, state: FSMContext):
    await message.answer("Введите интервал в часах:")
    await state.set_state(Form.waiting_for_interval)

@router.callback_query(F.data == "i_am_ok")
async def process_checkin(callback: types.CallbackQuery):
    async with httpx.AsyncClient() as client:
        await client.post(f"{SERVER_URL}/checkin", json={"telegram_id": callback.from_user.id})
    await callback.message.edit_text("✅ Таймер сброшен! Я спокоен.", reply_markup=None)
    await callback.answer("Статус обновлен")

async def handle_menu_buttons(message: types.Message, state: FSMContext):
    m = message.text
    if m == "📝 Записка": await edit_note(message, state)
    elif m == "👥 Контакты": await contact_menu(message, state)
    elif m == "⏱ Интервал": await set_interval(message, state)
    elif m == "💤 Режим сна": await set_dnd(message, state)
    elif m == "📊 Статус": await cmd_status(message)
    elif m == "🆘 SOS": await manual_sos(message)