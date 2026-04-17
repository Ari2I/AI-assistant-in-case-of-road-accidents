/**
 * Модальное окно карты Яндекс для выбора места ДТП
 */

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
        this.isInitialized = false;

        this.init();
    }

    init() {
        console.log('DtpMapModal.init() called');
        
        // Проверяем, загружен ли API Яндекс Карт
        if (typeof ymaps === 'undefined') {
            console.error('Yandex Maps API not loaded!');
            return;
        }

        // Ждём готовности API
        ymaps.ready(() => {
            this.isInitialized = true;
            console.log('Yandex Maps API ready');
            this.setupEventListeners();
        });
    }

    setupEventListeners() {
        const detectBtn = document.getElementById('detectLocationBtn');
        if (detectBtn) {
            detectBtn.addEventListener('click', (e) => this.openModal(e));
        }

        document.querySelectorAll('[data-close-map-modal]').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal());
        });

        const confirmBtn = document.getElementById('confirmMapSelection');
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.confirmSelection());
        }

        const overlay = document.querySelector('.map-modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.closeModal();
            });
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                const modal = document.getElementById('mapModal');
                if (modal && modal.style.display !== 'none') {
                    this.closeModal();
                }
            }
        });
    }

    openModal(e) {
        console.log('Opening map modal...');

        if (!this.isInitialized) {
            alert('Карта загружается. Попробуйте через несколько секунд.');
            return;
        }

        const modal = document.getElementById('mapModal');
        const mapContainer = document.getElementById('map');
        
        if (!modal || !mapContainer) {
            console.error('Modal or map container not found');
            return;
        }

        // Показываем модальное окно
        modal.style.display = 'block';
        document.body.style.overflow = 'hidden';
        console.log('Modal displayed');

        // Ждём пока контейнер получит размеры
        const checkContainer = () => {
            const rect = mapContainer.getBoundingClientRect();
            console.log('Container rect:', rect);
            
            if (rect.width > 100 && rect.height > 100) {
                console.log('Container has proper size, initializing map...');
                setTimeout(() => this.initMap(), 50);
            } else {
                console.log('Container too small, waiting...');
                setTimeout(checkContainer, 100);
            }
        };

        checkContainer();
    }

    initMap() {
        console.log('initMap() called');

        if (this.map) {
            this.map.destroy();
        }

        const mapContainer = document.getElementById('map');
        if (!mapContainer) {
            console.error('Map container not found');
            return;
        }

        const rect = mapContainer.getBoundingClientRect();
        console.log('Container size:', rect.width, 'x', rect.height);

        try {
            this.map = new ymaps.Map('map', {
                center: this.defaultCenter,
                zoom: this.defaultZoom,
                controls: ['zoomControl', 'geolocationControl']
            });

            // Ждём пока карта отрендерится
            this.map.events.add('sizechanged', () => {
                console.log('Map size changed');
            });

            // Принудительно обновляем размеры несколько раз
            const fixMapSize = () => {
                const ymapsEl = mapContainer.querySelector('.ymaps-2-1-79-map');
                if (ymapsEl) {
                    ymapsEl.style.height = '500px';
                    ymapsEl.style.width = '100%';
                    
                    // Также исправляем родительские элементы
                    const parent = ymapsEl.parentElement;
                    if (parent) {
                        parent.style.height = '500px';
                    }
                    
                    console.log('Fixed ymaps size to 500px');
                }
            };

            // Выполняем несколько раз с разными задержками
            setTimeout(() => {
                if (this.map) {
                    this.map.container.fitToViewport();
                    fixMapSize();
                }
            }, 100);
            
            setTimeout(fixMapSize, 300);
            setTimeout(fixMapSize, 500);

            console.log('Map created successfully');

            // Геолокация
            if (navigator.geolocation) {
                navigator.geolocation.getCurrentPosition(
                    (position) => {
                        const userCoords = [position.coords.latitude, position.coords.longitude];
                        this.map.setCenter(userCoords, 15);
                        this.placeMark(userCoords);
                        this.geocode(userCoords);
                    },
                    (error) => {
                        console.log('Геолокация недоступна:', error);
                    }
                );
            }

            this.map.events.add('click', (e) => {
                const coords = e.get('coords');
                this.placeMark(coords);
                this.geocode(coords);
            });

        } catch (error) {
            console.error('Error creating map:', error);
        }
    }

    placeMark(coords) {
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
                document.getElementById('confirmMapSelection').disabled = false;
                console.log('Address:', this.selectedAddress);
            } else {
                this.selectedAddress = null;
                document.getElementById('confirmMapSelection').disabled = true;
            }
        }).catch((error) => {
            console.error('Геокодирование ошибка:', error);
        });
    }

    confirmSelection() {
        if (!this.selectedAddress) {
            alert('Сначала выберите место на карте');
            return;
        }

        const euroPlaceInput = document.getElementById('euroPlace');
        if (euroPlaceInput) {
            euroPlaceInput.value = this.selectedAddress;
        }

        this.closeModal();

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
        if (modal) {
            modal.style.display = 'none';
            document.body.style.overflow = '';
        }

        if (this.map) {
            this.map.destroy();
            this.map = null;
            this.placemark = null;
        }

        this.selectedCoords = null;
        this.selectedAddress = null;
        document.getElementById('confirmMapSelection').disabled = true;
    }
}

// Авто-инициализация
document.addEventListener('DOMContentLoaded', () => {
    console.log('DOM loaded, initializing DtpMapModal...');
    window.dtpMap = new DtpMapModal();
});
