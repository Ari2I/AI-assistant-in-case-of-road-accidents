from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    patronymic = models.CharField("Отчество", max_length=150, blank=True)

    def __str__(self):
        return f"Профиль {self.user_id}"
