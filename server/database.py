import os
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import BigInteger, Integer, String, DateTime, JSON, Boolean, Float
from datetime import datetime

# Настройки подключения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/lonely_db")

engine = create_async_engine(DATABASE_URL, 
                             echo=False,
                             pool_size=20,
                             max_overflow=10
                             ) # echo=False, чтобы не мусорить в логах
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    
    # НАСТРОЙКИ ЮЗЕРА 
    # Активен ли мониторинг? (Если False - таймер не тикает)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Интервал проверки (в часах)
    check_interval: Mapped[float] = mapped_column(Float, default=24.0)
    
    # Часовой пояс (храним просто строку, например "Europe/Moscow" или смещение "+3")
    timezone: Mapped[str] = mapped_column(String, default="UTC")

    # Время "Не беспокоить" (строки "23:00", "08:00")
    dnd_start: Mapped[str | None] = mapped_column(String, nullable=True)
    dnd_end: Mapped[str | None] = mapped_column(String, nullable=True)

    # СОСТОЯНИЕ
    # Когда последний раз отмечался
    last_checkin: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Статус тревоги (0 - ок, 1 - ждем ответа, 2 - SOS отправлен)
    alert_status: Mapped[int] = mapped_column(Integer, default=0)

    # ДАННЫЕ ДЛЯ ЧП 
    # Список контактов: [{"name": "Мама", "phone": "+7900..."}]
    contacts: Mapped[list] = mapped_column(JSON, default=[])
    
    # Предсмертная записка
    death_note: Mapped[str | None] = mapped_column(String, nullable=True)

async def init_db():
    """Создает таблицы. Если надо сбросить базу - раскомментируй drop_all"""
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) 
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with async_session() as session:
        yield session
        
from sqlalchemy import update

async def reset_statuses_on_startup():
    """Сбрасывает все тревоги в 0 при запуске сервера"""
    async with async_session() as session:
        try:
            # Устанавливаем alert_status = 0 для всех
            stmt = update(User).values(alert_status=0)
            await session.execute(stmt)
            await session.commit()
            print("♻️ Все статусы тревоги сброшены в 0 (чистый запуск)")
        except Exception as e:
            print(f"❌ Ошибка при сбросе статусов: {e}")