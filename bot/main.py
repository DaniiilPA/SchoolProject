# bot/main.py
import asyncio
import os
import httpx
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
SERVER_URL = "http://127.0.0.1:8000"

bot = Bot(token=TOKEN)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    print(f"👤 Юзер {message.from_user.id} нажал /start")
    async with httpx.AsyncClient() as client:
        try:
            r = await client.post(f"{SERVER_URL}/register", json={"telegram_id": message.from_user.id})
            await message.answer("✅ Ты зарегистрирован!")
        except Exception as e:
            await message.answer(f"❌ Ошибка регистрации: {e}")

# ОБРАБОТЧИК КНОПКИ
@dp.callback_query(F.data == "i_am_ok")
async def process_i_am_ok(callback: types.CallbackQuery):
    print(f"🔘 Нажата кнопка 'Я В ПОРЯДКЕ' от {callback.from_user.id}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Шлем запрос на сервер
            resp = await client.post(f"{SERVER_URL}/checkin", json={"telegram_id": callback.from_user.id})
            
            if resp.status_code == 200:
                await callback.message.edit_text("✅ Таймер сброшен! Я спокоен.")
                await callback.answer("Статус обновлен")
            else:
                await callback.answer("Ошибка сервера!", show_alert=True)
        except Exception as e:
            print(f"❌ Ошибка при связи с сервером: {e}")
            await callback.answer("Не удалось связаться с сервером", show_alert=True)

async def main():
    print("🤖 БОТ ЗАПУЩЕН...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())