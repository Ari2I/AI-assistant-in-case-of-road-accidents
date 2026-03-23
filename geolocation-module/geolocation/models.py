from django.db import models
from django.contrib.auth.models import User


class DtpLocation(models.Model):
    """Модель места ДТП"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name='Пользователь')
    latitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='Широта')
    longitude = models.DecimalField(max_digits=9, decimal_places=6, verbose_name='Долгота')
    address = models.CharField(max_length=500, verbose_name='Адрес')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    class Meta:
        verbose_name = 'Место ДТП'
        verbose_name_plural = 'Места ДТП'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.address} ({self.created_at.strftime("%d.%m.%Y")})'
