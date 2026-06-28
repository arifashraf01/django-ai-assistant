from django.contrib import admin
from .models import ChatMessage, Document


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("__str__", "is_processed", "uploaded_at")
    list_filter = ("is_processed",)
    readonly_fields = ("uploaded_at",)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ("__str__", "document", "session_key", "created_at")
    list_filter = ("document",)
    readonly_fields = ("created_at",)
    search_fields = ("user_message", "ai_response")
