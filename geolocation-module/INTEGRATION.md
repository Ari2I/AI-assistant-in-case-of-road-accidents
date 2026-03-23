## Быстрая интеграция

### Шаг 1: Скопируйте файлы в ваш проект

```bash
# Скопируйте папку geolocation в ваш Django проект
cp -r geolocation-module/geolocation /path/to/your/project/

# Скопируйте статику
cp -r geolocation-module/static /path/to/your/project/
```

### Шаг 2: Установите зависимости

```bash
pip install -r geolocation-module/requirements.txt
```

### Шаг 3: Настройте `.env`

Скопируйте `.env.example` в ваш проект и добавьте API ключ:

```env
YANDEX_GEOCODER_API_KEY=ваш_ключ_здесь
```

Получите ключ на: https://developer.tech.yandex.ru/

### Шаг 4: Обновите `settings.py`

```python
# В INSTALLED_APPS добавьте:
INSTALLED_APPS = [
    # ...
    'geolocation',
]

# В начале файла добавьте импорты:
from dotenv import load_dotenv
import os

# После BASE_DIR загрузите .env:
load_dotenv()

# В TEMPLATES → OPTIONS → context_processors добавьте:
'geolocation.context_processors.yandex_api_key',

# В конец файла добавьте:
YANDEX_GEOCODER_API_KEY = os.getenv('YANDEX_GEOCODER_API_KEY', '')

STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### Шаг 5: Обновите `urls.py`

```python
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('geolocation/', include('geolocation.urls')),  # ← Добавить
    # ...
]

# В конец добавьте:
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
```

### Шаг 6: Примените миграции

```bash
python manage.py makemigrations geolocation
python manage.py migrate
```

### Шаг 7: Добавьте ссылки в навигацию

В вашем шаблоне (например, `accounts/templates/accounts/profile.html`):

```html
<div class="nav-links">
    <h3>🚗 ДТП Помощник</h3>
    <a href="{% url 'geolocation:select_location' %}">📍 Отметить место ДТП</a>
    <a href="{% url 'geolocation:location_history' %}">📋 История мест</a>
</div>

{% block content %}{% endblock %}
```

### Шаг 8: Запустите сервер

```bash
python manage.py runserver
```

Откройте http://127.0.0.1:8000/geolocation/select/

---

## 📁 Структура модуля

```
geolocation-module/
├── geolocation/                      # Django приложение
│   ├── migrations/
│   │   └── 0001_initial.py           # Миграция для модели
│   ├── templates/
│   │   └── geolocation/
│   │       ├── select_location.html  # Страница карты
│   │       └── location_history.html # История мест
│   ├── admin.py                      # Админка
│   ├── apps.py                       # Конфигурация
│   ├── context_processors.py         # API ключ для шаблонов
│   ├── models.py                     # Модель DtpLocation
│   ├── services.py                   # Яндекс Геокодер сервис
│   ├── urls.py                       # URL маршруты
│   └── views.py                      # Views
├── static/                           # Статические файлы
├── .env.example                      # Пример .env
├── .gitignore                        # Git игнор
├── requirements.txt                  # Python зависимости
├── INTEGRATION.md                    # Эта инструкция
└── README.md                         # Полная документация
```

---

## 🔌 API Endpoints

| Метод | URL | Описание |
|-------|-----|----------|
| GET | `/geolocation/select/` | Страница выбора места |
| POST | `/geolocation/api/get_address/` | Адрес по координатам |
| POST | `/geolocation/api/save_location/` | Сохранить место |
| GET | `/geolocation/history/` | История мест |

---

## 📊 Модель данных

### DtpLocation

```python
class DtpLocation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    address = models.CharField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField(blank=True, null=True)
```

---

## 🎨 Интеграция с вашим фронтендом

### Вариант 1: Кнопка с переходом на страницу

```html
<a href="/geolocation/select/" class="btn btn-primary">
    📍 Отметить место ДТП
</a>
```

### Вариант 2: Модальное окно с картой

Создайте modal в вашем шаблоне:

```html
<div id="map-modal" class="modal">
    <div class="modal-content">
        <span class="close">&times;</span>
        <h2>Отметьте место ДТП</h2>
        <div id="map" style="width: 100%; height: 400px;"></div>
        <input type="text" id="address" readonly>
        <button id="save-btn">Сохранить</button>
    </div>
</div>

<script src="https://api-maps.yandex.ru/2.1/?apikey={{ YANDEX_GEOCODER_API_KEY }}&lang=ru_RU"></script>
<script>
    // Код инициализации карты из geolocation/templates/geolocation/select_location.html
</script>
```

### Вариант 3: Через iframe

```html
<iframe src="/geolocation/select/" width="100%" height="600px"></iframe>
```

---

## 🔐 Доступ к данным пользователя

### В Django views:

```python
from django.contrib.auth.decorators import login_required

@login_required
def my_view(request):
    user = request.user
    email = user.email
    phone = user.username  # или user.phone если есть поле
```

### В JavaScript:

```javascript
// Из data-атрибутов
const userId = document.getElementById('user-data').dataset.userId;
const userEmail = document.getElementById('user-data').dataset.email;

// Или через AJAX
fetch('/accounts/api/user-data/')
    .then(r => r.json())
    .then(data => console.log(data.email));
```

---

## ⚙️ Настройка для продакшена

### .env (production)

```env
SECRET_KEY=ваш_секретный_ключ
DEBUG=False
ALLOWED_HOSTS=ваш-домен.ru
YANDEX_GEOCODER_API_KEY=ваш_ключ
DATABASE_URL=postgresql://user:pass@host:5432/dbname
```

### Команды для развёртывания:

```bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput
```

---