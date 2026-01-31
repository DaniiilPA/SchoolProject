import os
import httpx
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select, update
from dotenv import load_dotenv
from .database import async_session, User

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
scheduler = AsyncIOScheduler()

async def send_telegram_alert(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": chat_id, 
        "text": text,
        "reply_markup": {"inline_keyboard": [[{"text": "🟢 Я В ПОРЯДКЕ", "callback_data": "i_am_ok"}]]}
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            await client.post(url, json=payload)
        except Exception as e:
            print(f"❌ Ошибка отправки сообщения: {e}")

async def check_users_job():
    print(f"⏰ Проверка [{datetime.now().strftime('%H:%M:%S')}]")
    
    async with async_session() as db:
        result = await db.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()

        for user in users:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            time_passed = now - user.last_checkin

            # 1. Если время вышло, а мы еще не кипишуем (alert_status == 0)
            if time_passed > timedelta(seconds=30) and user.alert_status == 0:
                print(f"⚠️ ПРЕДУПРЕЖДЕНИЕ для {user.telegram_id}")
                await send_telegram_alert(user.telegram_id, "⏳ Ты давно не отмечался! У тебя есть 1 минута, прежде чем я подниму тревогу.")
                # Ставим статус "Ждем ответа"
                user.alert_status = 1
                await db.commit()

            # 2. Если мы уже ждем ответа больше 1 минуты (alert_status == 1)
            elif user.alert_status == 1 and time_passed > timedelta(seconds=90): # 30 сек + 60 сек ожидания
                print(f"🚨🚨🚨 SOS!!! Юзер {user.telegram_id} не отвечает!")
                
                # ИМИТАЦИЯ РАССЫЛКИ
                print(f"📢 [СЛУЖБА SOS] Рассылаю сообщения контактам юзера {user.telegram_id}...")
                print(f"📢 [СЛУЖБА SOS] Сообщение: 'Внимание! Юзер не выходил на связь более 24 часов. Последние координаты: неизвестны.'")
                
                user.alert_status = 2 # Статус "Тревога отправлена"
                await db.commit()
                
                await send_telegram_alert(user.telegram_id, "🆘 ТРЕВОГА ОТПРАВЛЕНА КОНТАКТАМ!")

async def start_scheduler():
    if not scheduler.get_jobs():
        scheduler.add_job(check_users_job, "interval", seconds=10)
    if not scheduler.running:
        scheduler.start()