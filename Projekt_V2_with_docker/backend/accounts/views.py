from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json
import re

from .forms import RegistrationForm


def register_view(request):
    """
    Регистрация нового пользователя
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('accounts:profile')
    else:
        form = RegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    """
    Вход пользователя
    """
    if request.user.is_authenticated:
        return redirect('accounts:profile')

    error = None

    if request.method == 'POST':
        contact = request.POST.get('contact', '').strip()
        password = request.POST.get('password', '')

        if contact and password:
            # Пробуем найти пользователя по email или телефону
            user = None

            # Проверка на email
            email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

            if re.match(email_pattern, contact):
                try:
                    user = User.objects.get(email=contact)
                except User.DoesNotExist:
                    pass
            else:
                # Для телефона используем username
                try:
                    user = User.objects.get(username=contact)
                except User.DoesNotExist:
                    pass

            if user:
                user = authenticate(request, username=user.username, password=password)
                if user:
                    login(request, user)
                    return redirect('accounts:profile')

        error = 'Неверный email/телефон или пароль'

    return render(request, 'accounts/login.html', {'error': error})


@login_required
def logout_view(request):
    """
    Выход пользователя
    """
    logout(request)
    return redirect('accounts:register')


@login_required
def profile_view(request):
    """
    Страница профиля пользователя
    """
    if request.method == 'POST':
        user = request.user
        data = json.loads(request.body)

        # Обновление данных
        if 'name' in data:
            user.first_name = data['name']
        if 'email' in data:
            user.email = data['email']
        if 'phone' in data:
            user.username = data['phone']

        # Смена пароля
        if 'password' in data and data['password']:
            if data['password'] == data.get('password_repeat', ''):
                user.set_password(data['password'])
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'Пароли не совпадают'
                }, status=400)

        user.save()
        return JsonResponse({'success': True})

    return render(request, 'accounts/profile.html')


@require_http_methods(['GET'])
@login_required
def user_data_api(request):
    """
    API для получения данных пользователя
    """
    user = request.user
    return JsonResponse({
        'id': user.id,
        'email': user.email,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
    })


@require_http_methods(['POST'])
@login_required
def save_europrotocol(request):
    """
    API для сохранения данных европротокола
    """
    try:
        data = json.loads(request.body)
        
        # Здесь можно сохранить данные в базу
        # Для примера просто логируем
        print("Europrotocol data:", data)
        
        return JsonResponse({
            'success': True,
            'message': 'Данные европротокола сохранены'
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
