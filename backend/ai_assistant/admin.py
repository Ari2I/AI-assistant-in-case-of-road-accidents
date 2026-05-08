from django.contrib import admin

from .models import ChatMessage


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "session_key", "source", "category", "created_at")
    list_filter = ("source", "category", "created_at")
    search_fields = ("query", "answer", "user__username", "user__email", "session_key")
    readonly_fields = ("created_at",)

# Register your models here.
