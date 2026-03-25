from django.conf import settings


def yandex_api_key(request):
    """Добавляет API ключ Яндекс в контекст всех шаблонов"""
    return {
        'YANDEX_GEOCODER_API_KEY': settings.YANDEX_GEOCODER_API_KEY,
    }
