from django.urls import path
from .views import chatbot, stream_chat

urlpatterns = [
    path('', chatbot, name='chatbot'),
    path('stream_chat/', stream_chat, name='stream_chat'),
]