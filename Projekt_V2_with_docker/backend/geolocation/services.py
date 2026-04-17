import requests
from django.conf import settings
from typing import Optional, Dict, Any


class YandexGeocoderService:
    """Сервис для работы с Яндекс Геокодер API"""

    BASE_URL = 'https://geocode-maps.yandex.ru/1.x/'

    def __init__(self):
        pass

    @property
    def api_key(self):
        key = settings.YANDEX_GEOCODER_API_KEY
        if not key:
            raise ValueError('YANDEX_GEOCODER_API_KEY не настроен в settings.py')
        return key
    
    def get_address_by_coords(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Получить адрес по координатам (reverse geocoding)
        
        Args:
            latitude: Широта
            longitude: Долгота
            
        Returns:
            Адрес в виде строки или None если не найдено
        """
        try:
            response = requests.get(
                self.BASE_URL,
                params={
                    'apikey': self.api_key,
                    'geocode': f'{longitude},{latitude}',
                    'format': 'json',
                    'lang': 'ru_RU',
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # Разбор ответа Яндекс
            geo_objects = data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember', [])
            
            if geo_objects:
                # Берём первый (самый точный) результат
                geo_object = geo_objects[0].get('GeoObject', {})
                address = geo_object.get('metaDataProperty', {}).get('GeocoderMetaData', {}).get('text', '')
                return address if address else None
            
            return None
            
        except requests.RequestException as e:
            print(f'Ошибка при запросе к Яндекс Геокодер: {e}')
            return None
    
    def get_coords_by_address(self, address: str) -> Optional[Dict[str, float]]:
        """
        Получить координаты по адресу (geocoding)
        
        Args:
            address: Адрес для поиска
            
        Returns:
            Словарь с координатами {'lat': ..., 'lng': ...} или None
        """
        try:
            response = requests.get(
                self.BASE_URL,
                params={
                    'apikey': self.api_key,
                    'geocode': address,
                    'format': 'json',
                    'lang': 'ru_RU',
                },
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            geo_objects = data.get('response', {}).get('GeoObjectCollection', {}).get('featureMember', [])
            
            if geo_objects:
                geo_object = geo_objects[0].get('GeoObject', {})
                pos = geo_object.get('Point', {}).get('pos', '')
                
                if pos:
                    lng, lat = pos.split()
                    return {'lat': float(lat), 'lng': float(lng)}
            
            return None
            
        except requests.RequestException as e:
            print(f'Ошибка при запросе к Яндекс Геокодер: {e}')
            return None


# Глобальный экземпляр сервиса
geocoder_service = YandexGeocoderService()
