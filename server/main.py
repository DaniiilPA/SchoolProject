from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from pydantic import BaseModel
from datetime import datetime

# Импортируем наши настройки из database.py
from .database import init_db, get_db, User, reset_statuses_on_startup
from .scheduler import start_scheduler, scheduler

# Жизненный цикл (Запуск/Остановка)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Сервер запускается...")
    await init_db()
    
    await reset_statuses_on_startup()
    
    await start_scheduler()
    print("⏰ Планировщик запущен")
    
    yield # Здесь сервер работает
    
    print("🛑 Выключение планировщика...")
    scheduler.shutdown(wait=False)
    print("🛑 Сервер остановлен")

app = FastAPI(lifespan=lifespan)

# Модели данных 
class UserRegister(BaseModel):
    telegram_id: int

class UserSettings(BaseModel):
    telegram_id: int
    check_interval: float | None = None
    death_note: str | None = None
    contacts: list | None = None
    dnd_start: str | None = None
    dnd_end: str | None = None

# API Ручки (Endpoints)

@app.get("/")
async def root():
    return {"status": "ok", "message": "Server is running"}

@app.post("/register")
async def register_user(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.telegram_id == user_data.telegram_id)
    result = await db.execute(query)
    existing_user = result.scalar_one_or_none()

    if existing_user:
        return {"status": "exists", "user_id": existing_user.telegram_id}

    new_user = User(telegram_id=user_data.telegram_id)
    db.add(new_user)
    
    try:
        await db.commit()
        return {"status": "created", "user_id": user_data.telegram_id}
    except Exception as e:
        await db.rollback()
        print(f"Ошибка БД: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при сохранении")

@app.post("/checkin")
async def checkin_user(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.telegram_id == user_data.telegram_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if user:
        if user.alert_status == 2:
            print(f"🔔 [ОТБОЙ] Юзер {user.telegram_id} сбросил статус SOS в ручном режиме.")

        # ПРИНУДИТЕЛЬНО обновляем всё:
        user.last_checkin = datetime.utcnow()
        user.alert_status = 0                 
        
        await db.commit()
        print(f"✅ Мониторинг для {user.telegram_id} возобновлен. Статус: 0, Таймер: 0с.")
        return {"status": "ok"}
    
    raise HTTPException(status_code=404, detail="User not found")

@app.post("/update_settings")
async def update_settings(data: UserSettings, db: AsyncSession = Depends(get_db)):
    print(f"⚙️ Обновление настроек для {data.telegram_id}")
    
    update_data = {}
    if data.check_interval is not None: update_data["check_interval"] = data.check_interval
    if data.death_note is not None: update_data["death_note"] = data.death_note
    if data.contacts is not None: update_data["contacts"] = data.contacts
    if data.dnd_start is not None: update_data["dnd_start"] = data.dnd_start
    if data.dnd_end is not None: update_data["dnd_end"] = data.dnd_end
    
    if not update_data:
        return {"status": "nothing_to_update"}

    stmt = update(User).where(User.telegram_id == data.telegram_id).values(**update_data)
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}

@app.get("/status/{telegram_id}")
async def get_status(telegram_id: int, db: AsyncSession = Depends(get_db)):
    query = select(User).where(User.telegram_id == telegram_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "check_interval": user.check_interval,
        "death_note": user.death_note or "Не установлена",
        "dnd": f"{user.dnd_start}-{user.dnd_end}" if user.dnd_start else "Не установлен",
        "contacts": user.contacts or []
    }

@app.post("/clear_contacts")
async def clear_contacts(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    stmt = update(User).where(User.telegram_id == user_data.telegram_id).values(contacts=[])
    await db.execute(stmt)
    await db.commit()
    print(f"🗑 Контакты очищены для {user_data.telegram_id}")
    return {"status": "cleared"}

@app.post("/sos_manual")
async def manual_sos_trigger(user_data: UserRegister, db: AsyncSession = Depends(get_db)):
    stmt = update(User).where(User.telegram_id == user_data.telegram_id).values(alert_status=2)
    await db.execute(stmt)
    await db.commit()
    print(f"🚨 РУЧНОЙ SOS для {user_data.telegram_id}")
    return {"status": "sos_activated"}

