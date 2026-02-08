FROM python:3.10-slim

WORKDIR /app

# Копируем требования из КОРНЯ проекта (мы укажем контекст сборки в compose)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код сервера
COPY server/ .

# Запуск
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]