from django.shortcuts import render
from ollama import chat
from .models import ChatMessage
from django.shortcuts import render, redirect



def chatbot(request):
    if request.method == "POST" and "clear_chat" in request.POST:
       ChatMessage.objects.all().delete()
       return redirect("chatbot")

    response_text = ""

    if request.method == "POST":
        user_message = request.POST.get("message")

        # Fetch last 5 conversations for memory
        recent_messages = ChatMessage.objects.order_by("-created_at")[:5]

        conversation = []

        # Reverse so oldest comes first
        for msg in reversed(recent_messages):
            conversation.append(
                {
                    "role": "user",
                    "content": msg.user_message
                }
            )

            conversation.append(
                {
                    "role": "assistant",
                    "content": msg.ai_response
                }
            )

        # Current user message
        conversation.append(
            {
                "role": "user",
                "content": user_message
            }
        )

        # Send to Ollama
        response = chat(
            model="gemma3:4b",
            messages=conversation
        )

        response_text = response["message"]["content"]

        # Save conversation
        ChatMessage.objects.create(
            user_message=user_message,
            ai_response=response_text
        )

    # Load all messages for UI
    messages = ChatMessage.objects.order_by("-created_at")

    return render(
        request,
        "chat/chat.html",
        {
            "response": response_text,
            "messages": messages
        }
    )