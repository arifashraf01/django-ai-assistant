from django.shortcuts import render
from ollama import chat
from .models import ChatMessage


def chatbot(request):
    response_text = ""

    if request.method == "POST":
        user_message = request.POST.get("message")

        response = chat(
            model="gemma3:4b",
            messages=[
                {
                    "role": "user",
                    "content": user_message
                }
            ]
        )

        response_text = response["message"]["content"]

        ChatMessage.objects.create(
            user_message=user_message,
            ai_response=response_text
        )

    messages = ChatMessage.objects.order_by("-created_at")

    return render(
        request,
        "chat/chat.html",
        {
            "response": response_text,
            "messages": messages
        }
    )