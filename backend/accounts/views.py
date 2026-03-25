from django.shortcuts import render

# Create your views here.

from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import json
from .models import Profile
from .forms import RegistrationForm, ProfileUpdateForm


@csrf_exempt
@require_http_methods(["POST"])
def register_view(request):
    try:
        data = json.loads(request.body)
        # Передаем данные в форму
        form = RegistrationForm(data)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return JsonResponse({'status': 'success', 'user_id': user.id})
        return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def login_view(request):
    try:
        data = json.loads(request.body)
        username = data.get('username') or data.get('contact')
        password = data.get('password')
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({'status': 'success', 'user_id': user.id})
        return JsonResponse({'status': 'error', 'message': 'Неверный логин или пароль'}, status=401)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
def logout_view(request):
    logout(request)
    return JsonResponse({'status': 'success'})


@csrf_exempt
@require_http_methods(["GET", "PUT"])
def profile_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'status': 'error', 'message': 'Требуется авторизация'}, status=401)

    if request.method == 'GET':
        profile = get_object_or_404(Profile, user=request.user)
        return JsonResponse({
            'name': f"{request.user.first_name} {request.user.last_name}".strip() or request.user.username,
            'email': request.user.email,
            'phone': profile.phone or ''
        })

    elif request.method == 'PUT':
        try:
            data = json.loads(request.body)
            # Для PUT запроса нужно добавить 'data' ключ для формы
            form = ProfileUpdateForm(data=data, instance=request.user)

            if form.is_valid():
                user = form.save()
                # Обновляем телефон в профиле отдельно
                if 'phone' in data:
                    user.profile.phone = data['phone']
                    user.profile.save()
                return JsonResponse({'status': 'success', 'message': 'Профиль обновлен'})
            return JsonResponse({'status': 'error', 'errors': form.errors}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)