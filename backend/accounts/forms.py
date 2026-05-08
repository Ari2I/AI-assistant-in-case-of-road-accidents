from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re

from .models import UserProfile


class RegistrationForm(UserCreationForm):
    """Форма регистрации с email/телефоном и паролем"""

    last_name = forms.CharField(
        label='Фамилия',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Иванов', 'autocomplete': 'family-name'})
    )

    first_name = forms.CharField(
        label='Имя',
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Иван', 'autocomplete': 'given-name'})
    )

    patronymic = forms.CharField(
        label='Отчество',
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Иванович', 'autocomplete': 'additional-name'})
    )
    
    contact = forms.CharField(
        label='Email или телефон',
        max_length=254,
        help_text='Введите email или номер телефона в формате +7XXXXXXXXXX',
        widget=forms.TextInput(attrs={'placeholder': 'you@example.com или +7XXXXXXXXXX', 'autocomplete': 'email'})
    )
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('last_name', 'first_name', 'patronymic', 'contact', 'password1', 'password2')
    
    def clean_contact(self):
        """Валидация email или телефона"""
        contact = self.cleaned_data.get('contact', '').strip()
        
        if not contact:
            raise forms.ValidationError('Введите email или номер телефона')
        
        # Проверка на email
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        # Проверка на телефон (начинается с +, затем 10-15 цифр)
        phone_pattern = r'^\+\d{10,15}$'
        
        if re.match(email_pattern, contact):
            # Проверяем, не занят ли email
            if User.objects.filter(email=contact).exists():
                raise forms.ValidationError('Этот email уже зарегистрирован')
            return contact
        elif re.match(phone_pattern, contact):
            # Для телефона будем хранить в username
            if User.objects.filter(username=contact).exists():
                raise forms.ValidationError('Этот номер телефона уже зарегистрирован')
            return contact
        else:
            raise forms.ValidationError(
                'Введите корректный email или номер телефона в формате +7XXXXXXXXXX'
            )
    
    def clean_password1(self):
        """Валидация пароля"""
        password = self.cleaned_data.get('password1')
        if len(password) < 8:
            raise forms.ValidationError('Пароль должен содержать минимум 8 символов')
        return password
    
    def save(self, commit=True):
        """Сохранение пользователя"""
        user = super().save(commit=False)
        contact = self.cleaned_data['contact']
        
        # Определяем, что ввёл пользователь
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        
        if re.match(email_pattern, contact):
            user.email = contact
            user.username = contact  # username используем как email для входа
        else:
            user.username = contact  # Для телефона используем как username

        user.first_name = self.cleaned_data['first_name'].strip()
        user.last_name = self.cleaned_data['last_name'].strip()
        
        if commit:
            user.save()
            UserProfile.objects.update_or_create(
                user=user,
                defaults={'patronymic': self.cleaned_data.get('patronymic', '').strip()},
            )
        return user
