from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json

from .models import DtpLocation
from .services import geocoder_service


@login_required
def select_location(request):
    """
    Страница выбора места ДТП на карте
    """
    return render(request, 'geolocation/select_location.html')


@require_http_methods(['POST'])
@login_required
def get_address_api(request):
    """
    API endpoint для получения адреса по координатам
    
    POST запрос с JSON:
    {
        "latitude": 55.751244,
        "longitude": 37.618423
    }
    
    Ответ:
    {
        "address": "Москва, Красная площадь, 1",
        "success": true
    }
    """
    try:
        data = json.loads(request.body)
        latitude = float(data.get('latitude', 0))
        longitude = float(data.get('longitude', 0))
        
        if not (latitude and longitude):
            return JsonResponse({
                'success': False,
                'error': 'Неверные координаты'
            }, status=400)
        
        address = geocoder_service.get_address_by_coords(latitude, longitude)
        
        if address:
            return JsonResponse({
                'success': True,
                'address': address
            })
        else:
            return JsonResponse({
                'success': False,
                'error': 'Адрес не найден'
            }, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(['POST'])
@login_required
def save_location(request):
    """
    API endpoint для сохранения места ДТП
    
    POST запрос с JSON:
    {
        "latitude": 55.751244,
        "longitude": 37.618423,
        "address": "Москва, Красная площадь, 1",
        "description": "Описание происшествия"
    }
    
    Ответ:
    {
        "success": true,
        "location_id": 1
    }
    """
    try:
        data = json.loads(request.body)
        latitude = float(data.get('latitude', 0))
        longitude = float(data.get('longitude', 0))
        address = data.get('address', '')
        description = data.get('description', '')
        
        if not (latitude and longitude and address):
            return JsonResponse({
                'success': False,
                'error': 'Неверные данные'
            }, status=400)
        
        # Сохраняем место ДТП
        location = DtpLocation.objects.create(
            user=request.user,
            latitude=latitude,
            longitude=longitude,
            address=address,
            description=description
        )
        
        return JsonResponse({
            'success': True,
            'location_id': location.id,
            'message': 'Место ДТП сохранено'
        })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def location_history(request):
    """
    Страница истории мест ДТП пользователя
    """
    locations = DtpLocation.objects.filter(user=request.user)
    return render(request, 'geolocation/location_history.html', {'locations': locations})
