# 📍 Интеграция карты выбора места ДТП

## Описание

Модальное окно с картой Яндекс для выбора места ДТП и автоматического определения адреса.

---

## 📋 Требования

- API ключ Яндекс (JavaScript API и HTTP Геокодер)
- Обязательно в настройках ключа указать: Ограничение по IP-адресам - 127.0.0.1 и Ограничение по HTTP Referer - localhost (пока что так, нужно бужет понять как это не на локальном хосте юзать, еще не разбирался)

---

## 🚀 Быстрый старт

### 1. Подключить скрипт и стили

```html
<!-- В <head> или перед </body> -->
<link rel="stylesheet" href="/static/geolocation/css/map-modal.css">
```

```html
<!-- Перед </body> -->
<script src="https://api-maps.yandex.ru/2.1/?apikey=YOUR_API_KEY&lang=ru_RU" type="text/javascript"></script>
<script src="/static/geolocation/js/map-modal.js"></script>
```

---

### 2. Добавить кнопку вызова карты

```html
<button 
    type="button" 
    class="btn btn-primary" 
    data-open-map-modal
    data-target-input="id_address_input"
    data-target-lat="id_latitude"
    data-target-lng="id_longitude"
>
    📍 Выбрать место на карте
</button>
```

**Атрибуты:**
- `data-target-input` — ID поля, куда записать адрес
- `data-target-lat` — ID поля для широты (скрытое)
- `data-target-lng` — ID поля для долготы (скрытое)

---

### 3. Добавить скрытые поля в форму

```html
<form method="post">
    <!-- Поле адреса (только чтение) -->
    <div class="form-group">
        <label for="id_address">Адрес:</label>
        <input 
            type="text" 
            id="id_address" 
            name="address" 
            class="form-control" 
            readonly 
            placeholder="Выберите на карте"
        >
    </div>
    
    <!-- Скрытые поля для координат -->
    <input type="hidden" id="id_latitude" name="latitude">
    <input type="hidden" id="id_longitude" name="longitude">
    
    <!-- Остальные поля формы -->
    <button type="submit">Сохранить</button>
</form>
```

---

## 🎨 HTML модального окна

```html
<!-- Модальное окно карты -->
<div id="mapModal" class="map-modal" style="display: none;">
    <div class="map-modal-overlay">
        <div class="map-modal-content">
            <div class="map-modal-header">
                <h2>📍 Отметьте место на карте</h2>
                <button class="map-modal-close" data-close-map-modal>&times;</button>
            </div>
            
            <div id="map" class="map-container"></div>
            
            <div class="map-modal-footer">
                <button class="btn btn-secondary" data-close-map-modal>Отмена</button>
                <button class="btn btn-primary" id="confirmMapSelection" disabled>
                    ✅ Подтвердить
                </button>
            </div>
        </div>
    </div>
</div>
```

---

## 📦 JavaScript (готовый компонент)

### Вариант 1: Vanilla JS (без зависимостей)

```javascript
// /static/geolocation/js/map-modal.js

class DtpMapModal {
    constructor(options = {}) {
        this.apiKey = options.apiKey || '';
        this.defaultCenter = options.defaultCenter || [55.751244, 37.618423];
        this.defaultZoom = options.defaultZoom || 10;
        
        this.map = null;
        this.placemark = null;
        this.selectedCoords = null;
        this.selectedAddress = null;
        
        this.targetInput = null;
        this.targetLat = null;
        this.targetLng = null;
        
        this.init();
    }
    
    init() {
        // Ждём загрузки Яндекс API
        if (typeof ymaps === 'undefined') {
            console.error('Yandex Maps API not loaded');
            return;
        }
        
        ymaps.ready(() => this.setupEventListeners());
    }
    
    setupEventListeners() {
        // Открытие модального окна
        document.querySelectorAll('[data-open-map-modal]').forEach(btn => {
            btn.addEventListener('click', (e) => this.openModal(e));
        });
        
        // Закрытие модального окна
        document.querySelectorAll('[data-close-map-modal]').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });
        
        // Подтверждение выбора
        const confirmBtn = document.getElementById('confirmMapSelection');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmSelection());
        }
        
        // Закрытие по клику на overlay
        const overlay = document.querySelector('.map-modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.closeModal();
            });
        }
    }
    
    openModal(e) {
        const button = e.currentTarget;
        
        // Получаем целевые поля из data-атрибутов
        const targetInputId = button.dataset.targetInput;
        const targetLatId = button.dataset.targetLat;
        const targetLngId = button.dataset.targetLng;
        
        this.targetInput = document.getElementById(targetInputId);
        this.targetLat = document.getElementById(targetLatId);
        this.targetLng = document.getElementById(targetLngId);
        
        // Показываем модальное окно
        const modal = document.getElementById('mapModal');
        if (modal) modal.style.display = 'block';
        
        // Инициализируем карту
        this.initMap();
    }
    
    initMap() {
        if (this.map) {
            this.map.destroy();
        }
        
        this.map = new ymaps.Map('map', {
            center: this.defaultCenter,
            zoom: this.defaultZoom,
            controls: ['zoomControl', 'geolocationControl']
        });
        
        // Клик по карте
        this.map.events.add('click', (e) => {
            const coords = e.get('coords');
            this.setPlacemark(coords);
            this.geocode(coords);
        });
    }
    
    setPlacemark(coords) {
        if (this.placemark) {
            this.map.geoObjects.remove(this.placemark);
        }
        
        this.placemark = new ymaps.Placemark(coords, {
            hintContent: 'Место ДТП'
        }, {
            preset: 'islands#redCarIcon'
        });
        
        this.map.geoObjects.add(this.placemark);
        this.selectedCoords = coords;
    }
    
    geocode(coords) {
        ymaps.geocode(coords, { lang: 'ru_RU' }).then((res) => {
            const geoObject = res.geoObjects.get(0);
            
            if (geoObject) {
                this.selectedAddress = geoObject.getAddressLine();
                document.getElementById('address').value = this.selectedAddress;
                document.getElementById('confirmMapSelection').disabled = false;
            } else {
                this.selectedAddress = null;
                document.getElementById('address').value = 'Адрес не определён';
                document.getElementById('confirmMapSelection').disabled = true;
            }
        }).catch((error) => {
            console.error('Ошибка геокодирования:', error);
            document.getElementById('address').value = 'Ошибка определения адреса';
            document.getElementById('confirmMapSelection').disabled = true;
        });
    }
    
    confirmSelection() {
        if (!this.selectedCoords || !this.selectedAddress) {
            alert('Сначала выберите место на карте');
            return;
        }
        
        // Заполняем целевые поля
        if (this.targetInput) {
            this.targetInput.value = this.selectedAddress;
        }
        if (this.targetLat) {
            this.targetLat.value = this.selectedCoords[0];
        }
        if (this.targetLng) {
            this.targetLng.value = this.selectedCoords[1];
        }
        
        // Закрываем модальное окно
        this.closeModal();
        
        // Вызываем кастомное событие (опционально)
        const event = new CustomEvent('mapLocationSelected', {
            detail: {
                address: this.selectedAddress,
                latitude: this.selectedCoords[0],
                longitude: this.selectedCoords[1]
            }
        });
        document.dispatchEvent(event);
    }
    
    closeModal() {
        const modal = document.getElementById('mapModal');
        if (modal) modal.style.display = 'none';
        
        if (this.map) {
            this.map.destroy();
            this.map = null;
        }
        
        this.selectedCoords = null;
        this.selectedAddress = null;
    }
}

// Авто-инициализация
document.addEventListener('DOMContentLoaded', () => {
    window.dtpMap = new DtpMapModal({
        apiKey: window.YANDEX_API_KEY || ''
    });
});
```

---

### Вариант 2: jQuery (если используется)

```javascript
// /static/geolocation/js/map-modal-jquery.js

(function($) {
    'use strict';
    
    $.fn.dtpMapModal = function(options) {
        const settings = $.extend({
            apiKey: '',
            defaultCenter: [55.751244, 37.618423],
            defaultZoom: 10
        }, options);
        
        let map = null;
        let placemark = null;
        let selectedCoords = null;
        let selectedAddress = null;
        let $targetInput, $targetLat, $targetLng;
        
        // Инициализация карты
        function initMap() {
            if (map) map.destroy();
            
            map = new ymaps.Map('map', {
                center: settings.defaultCenter,
                zoom: settings.defaultZoom,
                controls: ['zoomControl', 'geolocationControl']
            });
            
            map.events.add('click', function(e) {
                const coords = e.get('coords');
                setPlacemark(coords);
                geocode(coords);
            });
        }
        
        function setPlacemark(coords) {
            if (placemark) map.geoObjects.remove(placemark);
            
            placemark = new ymaps.Placemark(coords, {
                hintContent: 'Место ДТП'
            }, { preset: 'islands#redCarIcon' });
            
            map.geoObjects.add(placemark);
            selectedCoords = coords;
        }
        
        function geocode(coords) {
            ymaps.geocode(coords, { lang: 'ru_RU' }).then(function(res) {
                const geoObject = res.geoObjects.get(0);
                
                if (geoObject) {
                    selectedAddress = geoObject.getAddressLine();
                    $('#address').val(selectedAddress);
                    $('#confirmMapSelection').prop('disabled', false);
                } else {
                    selectedAddress = null;
                    $('#address').val('Адрес не определён');
                    $('#confirmMapSelection').prop('disabled', true);
                }
            });
        }
        
        // Обработчики событий
        $(document)
            .on('click', '[data-open-map-modal]', function(e) {
                const $btn = $(e.currentTarget);
                
                $targetInput = $('#' + $btn.data('targetInput'));
                $targetLat = $('#' + $btn.data('targetLat'));
                $targetLng = $('#' + $btn.data('targetLng'));
                
                $('#mapModal').fadeIn(200);
                initMap();
            })
            .on('click', '[data-close-map-modal]', function() {
                $('#mapModal').fadeOut(200);
                if (map) {
                    map.destroy();
                    map = null;
                }
            })
            .on('click', '#confirmMapSelection', function() {
                if (!selectedCoords || !selectedAddress) {
                    alert('Сначала выберите место на карте');
                    return;
                }
                
                if ($targetInput.length) $targetInput.val(selectedAddress);
                if ($targetLat.length) $targetLat.val(selectedCoords[0]);
                if ($targetLng.length) $targetLng.val(selectedCoords[1]);
                
                $('#mapModal').fadeOut(200);
                
                // Событие для внешней логики
                $(document).trigger('mapLocationSelected', [{
                    address: selectedAddress,
                    latitude: selectedCoords[0],
                    longitude: selectedCoords[1]
                }]);
            });
        
        return this;
    };
    
    // Авто-инициализация
    $(document).ready(function() {
        $.fn.dtpMapModal();
    });
    
})(jQuery);
```

---

## 🎨 CSS стили

```css
/* /static/geolocation/css/map-modal.css */

.map-modal {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    z-index: 9999;
}

.map-modal-overlay {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: center;
    justify-content: center;
}

.map-modal-content {
    background: white;
    border-radius: 8px;
    width: 90%;
    max-width: 900px;
    max-height: 90vh;
    overflow: hidden;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}

.map-modal-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 15px 20px;
    border-bottom: 1px solid #e0e0e0;
}

.map-modal-header h2 {
    margin: 0;
    font-size: 18px;
    color: #333;
}

.map-modal-close {
    background: none;
    border: none;
    font-size: 28px;
    cursor: pointer;
    color: #999;
    padding: 0;
    width: 30px;
    height: 30px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.map-modal-close:hover {
    color: #333;
}

.map-container {
    width: 100%;
    height: 450px;
}

.map-modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: 10px;
    padding: 15px 20px;
    border-top: 1px solid #e0e0e0;
    background: #f8f9fa;
}

.btn {
    padding: 10px 20px;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
}

.btn-primary {
    background: #007bff;
    color: white;
}

.btn-primary:hover:not(:disabled) {
    background: #0056b3;
}

.btn-primary:disabled {
    background: #ccc;
    cursor: not-allowed;
}

.btn-secondary {
    background: #6c757d;
    color: white;
}
```

---

## 📡 API Endpoints (Backend)

### Получить адрес по координатам

**POST** `/geolocation/api/get_address/`

**Request:**
```json
{
    "latitude": 55.751244,
    "longitude": 37.618423
}
```

**Response:**
```json
{
    "success": true,
    "address": "Москва, Красная площадь, 1"
}
```

---

## 🎯 Примеры использования

### Пример 1: Простая форма

```html
<form method="post">
    <div class="form-group">
        <label>Адрес:</label>
        <div class="input-group">
            <input type="text" id="address" name="address" class="form-control" readonly>
            <button type="button" data-open-map-modal 
                    data-target-input="address"
                    data-target-lat="latitude"
                    data-target-lng="longitude"
                    class="btn btn-secondary">
                📍 Карта
            </button>
        </div>
        <input type="hidden" id="latitude" name="latitude">
        <input type="hidden" id="longitude" name="longitude">
    </div>
    <button type="submit">Сохранить</button>
</form>
```

### Пример 2: С обработкой события

```javascript
document.addEventListener('mapLocationSelected', function(e) {
    console.log('Выбран адрес:', e.detail.address);
    console.log('Координаты:', e.detail.latitude, e.detail.longitude);
    
    // Можно вызвать дополнительную логику
    // Например, показать ближайший адрес на сервере
    fetch('/api/validate-address/', {
        method: 'POST',
        body: JSON.stringify(e.detail)
    });
});
```

### Пример 3: React/Vue интеграция

```jsx
// React компонент
function AddressInput({ value, onChange }) {
    const handleMapSelect = (e) => {
        onChange({
            address: e.detail.address,
            latitude: e.detail.latitude,
            longitude: e.detail.longitude
        });
    };
    
    useEffect(() => {
        document.addEventListener('mapLocationSelected', handleMapSelect);
        return () => document.removeEventListener('mapLocationSelected', handleMapSelect);
    }, []);
    
    return (
        <div>
            <input type="text" value={value.address} readOnly />
            <button 
                data-open-map-modal
                data-target-input="address"
                data-target-lat="latitude"
                data-target-lng="longitude"
            >
                📍 Карта
            </button>
            <input type="hidden" id="address" />
            <input type="hidden" id="latitude" />
            <input type="hidden" id="longitude" />
        </div>
    );
}
```

---

## ⚠️ Важные замечания

1. **API ключ** должен быть настроен для домена, на котором работает приложение
2. **JavaScript API** загружается асинхронно — убедитесь, что `ymaps` доступен перед использованием
3. **CORS** — если используете backend API для геокодирования, убедитесь, что CSRF токены настроены
4. **Мобильные устройства** — модальное окно адаптировано для мобильных (width: 90%)

---

