import os
import httpx
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from dotenv import load_dotenv
from    database import async_session, User

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
            print(f"❌ Ошибка отправки: {e}")

def is_now_in_dnd(start_str, end_str):
    if not start_str or not end_str:
        return False
    now_time = datetime.now().strftime("%H:%M")
    if start_str <= end_str:
        return start_str <= now_time <= end_str
    else:
        return now_time >= start_str or now_time <= end_str

async def check_users_job():
    now = datetime.utcnow()
    print(f"⏰ --- СЕССИЯ ПРОВЕРКИ {now.strftime('%H:%M:%S')} ---")
    
    async with async_session() as db:
        result = await db.execute(select(User).where(User.is_active == True))
        users = result.scalars().all()

        if not users:
            print("ℹ️ В базе нет активных пользователей.")

        for user in users:
            # 1. Проверка сна
            if is_now_in_dnd(user.dnd_start, user.dnd_end):
                print(f"💤 Юзер {user.telegram_id} спит ({user.dnd_start}-{user.dnd_end}). Пропускаю.")
                continue

            # 2. Расчет времени
            time_passed = now - user.last_checkin
            seconds_passed = time_passed.total_seconds()
            threshold = user.check_interval * 3600

            print(f"👤 Юзер {user.telegram_id}: прошло {seconds_passed:.0f}с / порог {threshold:.0f}с | статус: {user.alert_status}")

            # 3. Логика
            if seconds_passed > threshold and user.alert_status == 0:
                print(f"⚠️ ТРИГГЕР: Шлю предупреждение юзеру {user.telegram_id}")
                await send_telegram_alert(user.telegram_id, f"⏳ Время вышло! Ты в порядке?")
                user.alert_status = 1
                user.last_checkin = datetime.utcnow()
                await db.commit()

            elif seconds_passed > 60 and user.alert_status == 1: # Даем 60 сек на ответ
                print(f"🚨 ТРИГГЕР: SOS для {user.telegram_id}")
                user.alert_status = 2
                await db.commit()
                await send_telegram_alert(user.telegram_id, "🆘 ТРЕВОГА ОТПРАВЛЕНА!")

async def start_scheduler():
    if not scheduler.get_jobs():
        scheduler.add_job(check_users_job, "interval", seconds=10)
    if not scheduler.running:
        scheduler.start()
        print("⏰ Планировщик запущен.")