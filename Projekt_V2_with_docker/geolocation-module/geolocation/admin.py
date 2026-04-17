from django.contrib import admin
from .models import DtpLocation


@admin.register(DtpLocation)
class DtpLocationAdmin(admin.ModelAdmin):
    list_display = ('user', 'address', 'created_at')
    list_filter = ('user', 'created_at')
    search_fields = ('address', 'user__username', 'user__email')
    readonly_fields = ('latitude', 'longitude', 'created_at')
