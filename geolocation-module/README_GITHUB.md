# 🗺️ Модуль геолокации для ДТП Помощника

Готовый модуль для Django с функционалом выбора места ДТП на карте Яндекс.

---

## 🚀 Быстрый старт

### 1. Установите зависимости

```bash
pip install -r requirements.txt
```

### 2. Настройте `.env`

```bash
cp .env.example .env
```

Откройте `.env` и вставьте ваш API ключ Яндекс:

```env
YANDEX_GEOCODER_API_KEY=ваш_ключ_здесь
```

**Получить ключ:** https://developer.tech.yandex.ru/

### 3. Скопируйте в ваш Django проект

```bash
# Скопируйте приложение geolocation
cp -r geolocation /path/to/your/django/project/

# Скопируйте статику
cp -r static /path/to/your/django/project/
```

### 4. Интегрируйте в проект

Следуйте инструкции в **`INTEGRATION.md`**

---

## 📚 Документация

- **`INTEGRATION.md`** — пошаговая инструкция по интеграции
- **`README.md`** — полная документация (в папке geolocation-module)

---

## 🎯 Что внутри

- ✅ Интерактивная карта Яндекс
- ✅ Автоматическое определение адреса по координатам
- ✅ Сохранение мест ДТП в базу данных
- ✅ История мест пользователя
- ✅ Интеграция с авторизацией Django

---

## 📦 Структура

```
geolocation-module/
├── geolocation/              # Django приложение
│   ├── models.py             # Модель DtpLocation
│   ├── views.py              # Views для API и страниц
│   ├── services.py           # Сервис Яндекс Геокодера
│   ├── urls.py               # URL маршруты
│   ├── admin.py              # Админка
│   └── templates/            # HTML шаблоны
├── static/                   # CSS/JS (если есть)
├── .env.example              # Пример .env
├── .gitignore                # Git игнор
├── requirements.txt          # Зависимости
├── INTEGRATION.md            # Инструкция по интеграции
└── README.md                 # Этот файл
```

---

## 🔧 Требования

- Python 3.10+
- Django 4.0+
- Яндекс Карты API ключ

---

## 📄 Лицензия

MIT

---

## 🤝 Поддержка

Вопросы и предложения: [ваш контакт]
