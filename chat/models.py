
from django.db import models

class ChatMessage(models.Model):
    user_message = models.TextField()
    ai_response = models.TextField()
    document = models.ForeignKey(
        'Document',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='chat_messages'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.user_message[:50]
    
class Document(models.Model):
    file = models.FileField(upload_to="documents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return self.file.name
    
    class Meta:
        ordering = ['-uploaded_at']