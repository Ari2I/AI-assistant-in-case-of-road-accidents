# backend/Dockerfile
FROM python:3.12-slim

# Устанавливаем системные зависимости для ML-библиотек
RUN apt-get update && apt-get install -y \
    build-essential \
    libmagic1 \
    pandoc \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
# unstructured[md] может падать — если так, замените на unstructured без [md]
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . .

# Создаём папки для статики и медиа, если их нет
RUN mkdir -p staticfiles media ai_assistant/chroma_db

# Переменные окружения по умолчанию (можно переопределить через docker-compose)
ENV PYTHONUNBUFFERED=1 \
    DJANGO_SECRET_KEY=django-insecure-dev-key-change-in-prod \
    DEBUG=False \
    ALLOWED_HOSTS=* \
    GIGA_AUTH= \
    YANDEX_GEOCODER_API_KEY=

# Собираем статику при сборке образа (опционально)
RUN python manage.py collectstatic --noinput || true

# Открываем порт
EXPOSE 8000

# Команда запуска через Gunicorn (продакшен-сервер)
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn dtp_project.wsgi:application --bind 0.0.0.0:8000 --workers 2"]
