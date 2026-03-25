from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re


class RegistrationForm(UserCreationForm):
    """Форма регистрации с email/телефоном и паролем"""
    
    contact = forms.CharField(
        label='Email или телефон',
        max_length=254,
        help_text='Введите email или номер телефона в формате +7XXXXXXXXXX'
    )
    
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('contact', 'password1', 'password2')
    
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
        
        if commit:
            user.save()
        return user
