# Цифровой ассистент при ДТП — Django приложение

Веб-приложение для оформления ДТП с интеграцией карты Яндекс для выбора места происшествия.

## Структура проекта

```
Project_V1/
├── backend/                 # Django бэкенд
│   ├── accounts/           # Приложение регистрации/авторизации
│   ├── dtp_project/        # Основной Django проект
│   ├── geolocation/        # Приложение карты (Яндекс Карты)
│   ├── static/             # Статические файлы (CSS, JS, изображения)
│   ├── templates/          # Django шаблоны
│   ├── media/              # Загруженные файлы
│   ├── manage.py           # Django управление
│   ├── requirements.txt    # Python зависимости
│   └── .env                # Переменные окружения (API ключи)
├── frontend/               # Исходные файлы frontend (для разработки)
└── geolocation-module/     # Исходный модуль геолокации (документация)
```

## Быстрый старт

### 1. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### 2. Настройка API ключа

1. Получите API ключ Яндекс Геокодера: https://developer.tech.yandex.ru/
2. Откройте файл `backend/.env`
3. Добавьте ваш ключ:

```env
YANDEX_GEOCODER_API_KEY=ваш_ключ_здесь
```

### 3. Применение миграций

```bash
cd backend
python manage.py migrate
```

### 4. Запуск сервера

```bash
python manage.py runserver
```

Откройте в браузере: **http://127.0.0.1:8000/**

## Возможности

### ✅ Реализовано

1. **Регистрация/Авторизация**
   - Регистрация по email или телефону
   - Вход в систему
   - Страница профиля

2. **Пошаговый мастер оформления ДТП**
   - Выбор типа происшествия (Серьёзное ДТП / Европротокол)
   - Инструкция по шагам
   - Загрузка фотографий
   - Форма европротокола

3. **Карта для выбора места ДТП**
   - Модальное окно с картой Яндекс
   - Автоматическое определение геолокации
   - Выбор места кликом по карте
   - Геокодирование координат в адрес

4. **Мультиязычность**
   - Русский (RU)
   - Английский (EN)

5. **Профиль пользователя**
   - Редактирование данных
   - Смена пароля

### 🚧 В разработке

- Чат с ИИ-ассистентом
- Расчёт суммы страховой выплаты
- Сохранение данных европротокола в базу
- История мест ДТП

## API Endpoints

### Accounts

| Метод | URL | Описание |
|-------|-----|----------|
| GET/POST | `/accounts/register/` | Регистрация |
| GET/POST | `/accounts/login/` | Вход |
| GET | `/accounts/logout/` | Выход |
| GET/POST | `/accounts/profile/` | Профиль |
| GET | `/accounts/api/user-data/` | Данные пользователя (JSON) |
| POST | `/accounts/api/save-europrotocol/` | Сохранение европротокола |

### Geolocation

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/geolocation/select/` | Страница выбора места |
| POST | `/geolocation/api/get_address/` | Получить адрес по координатам |
| POST | `/geolocation/api/save_location/` | Сохранить место ДТП |
| GET | `/geolocation/history/` | История мест |

## Структура шаблонов

```
templates/
├── base.html              # Базовый шаблон
└── accounts/
    ├── register.html      # Страница регистрации
    ├── login.html         # Страница входа
    └── profile.html       # Главный шаблон с приложением
```

## Статические файлы

```
static/
├── css/
│   ├── styles.css        # Основные стили приложения
│   └── map-modal.css     # Стили модального окна карты
├── js/
│   ├── app.js            # Логика frontend приложения
│   └── map-modal.js      # Логика карты
└── png/                  # Изображения для шагов
```

## Модель данных

### DtpLocation (Место ДТП)

```python
class DtpLocation(models.Model):
    user = ForeignKey(User)           # Пользователь
    latitude = DecimalField()         # Широта
    longitude = DecimalField()        # Долгота
    address = CharField()             # Адрес
    created_at = DateTimeField()      # Дата создания
    description = TextField()         # Описание (опционально)
```

## Требования

- Python 3.10+
- Django 6.0+
- API ключ Яндекс Геокодера

## Разработка

### Добавление новых стилей

1. Откройте `static/css/styles.css`
2. Добавьте стили
3. Обновления применятся автоматически при `DEBUG = True`

### Добавление новых JS функций

1. Откройте `static/js/app.js` (основная логика)
2. Или `static/js/map-modal.js` (карта)
3. Обновления применятся автоматически

### Изменение шаблонов

1. Откройте `templates/accounts/profile.html`
2. Внесите изменения
3. Перезагрузите страницу

## Развёртывание (Production)

### 1. Настройка .env

```env
SECRET_KEY=ваш_секретный_ключ
DEBUG=False
ALLOWED_HOSTS=ваш-домен.ru
YANDEX_GEOCODER_API_KEY=ваш_ключ
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### 2. Сборка статики

```bash
python manage.py collectstatic --noinput
```

### 3. Миграции

```bash
python manage.py migrate --noinput
```

### 4. Запуск через Gunicorn/uWSGI

```bash
gunicorn dtp_project.wsgi:application --bind 0.0.0.0:8000
```

## Лицензия

Проект создан для образовательных целей.

## Контакты

По вопросам интеграции и доработок обращайтесь к разработчику.
