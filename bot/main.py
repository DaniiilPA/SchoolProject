import asyncio
import os
import logging
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

# Импортируем наш роутер из соседнего файла
from handlers import router

load_dotenv()

async def main():
    # Настройка логов
    logging.basicConfig(level=logging.INFO)
    
    bot = Bot(token=os.getenv("BOT_TOKEN"))
    dp = Dispatcher()

    # Подключаем обработчики из handlers.py
    dp.include_router(router)

    print("🤖 Бот запущен (через handlers.py)...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())