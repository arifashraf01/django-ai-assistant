from ollama import chat

response = chat(
    model="gemma3:4b",
    messages=[
        {
            "role": "user",
            "content": "Reply with exactly: Django AI Assistant is working"
        }
    ]
)

print(response["message"]["content"])