import os
from django.db import models


class Document(models.Model):
    file = models.FileField(upload_to="documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self) -> str:
        return os.path.basename(self.file.name)


class ChatMessage(models.Model):
    user_message = models.TextField()
    ai_response = models.TextField()
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="chat_messages",
    )
    # Scopes messages to a browser session so different users don't share history
    session_key = models.CharField(max_length=100, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.user_message[:60]