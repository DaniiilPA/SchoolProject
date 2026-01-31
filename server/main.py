from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update # <--- Добавил update
from pydantic import BaseModel
from datetime import datetime # <--- Добавил datetime

# Импортируем наши настройки из database.py
from .database import init_db, get_db, User
from .scheduler import start_scheduler, scheduler

# Жизненный цикл (Запуск/Остановка)
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Сервер запускается...")
    await init_db()
    
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

# API Ручки (Endpoints

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
    print(f"📥 Получен чекин от {user_data.telegram_id}")
    
    stmt = (
        update(User)
        .where(User.telegram_id == user_data.telegram_id)
        .values(
            last_checkin=datetime.utcnow(),
            alert_status=0 
        )
    )
    
    await db.execute(stmt)
    await db.commit()
    return {"status": "ok"}