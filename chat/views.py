from django.shortcuts import render, redirect
from ollama import chat
from .models import ChatMessage, Document
from .forms import DocumentForm


def chatbot(request):

    # Clear chat
    if request.method == "POST" and "clear_chat" in request.POST:
        ChatMessage.objects.all().delete()
        return redirect("chatbot")

    response_text = ""

    # PDF Upload
    if request.method == "POST" and request.FILES.get("file"):
        document_form = DocumentForm(
            request.POST,
            request.FILES
        )

        if document_form.is_valid():
            document_form.save()

        messages = ChatMessage.objects.order_by("-created_at")

        return render(
            request,
            "chat/chat.html",
            {
                "response": response_text,
                "messages": messages,
                "document_form": DocumentForm(),
            }
        )

    # Chat Message
    if request.method == "POST" and request.POST.get("message"):

        user_message = request.POST.get("message")

        recent_messages = ChatMessage.objects.order_by("-created_at")[:5]

        conversation = []

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

        conversation.append(
            {
                "role": "user",
                "content": user_message
            }
        )

        response = chat(
            model="gemma3:4b",
            messages=conversation
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
            "messages": messages,
            "document_form": DocumentForm(),
        }
    )