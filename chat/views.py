from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ChatMessage, Document
from .forms import DocumentForm
from .pdf_utils import extract_text_from_pdf, chunk_text
from .rag_utils import store_document_chunks, get_rag_response


def chatbot(request):
    """
    Main chatbot view handling:
    - PDF upload and processing
    - RAG-based chat with context from uploaded PDFs
    - Chat history management
    """
    
    response_text = ""
    active_document = None

    # Clear chat history
    if request.method == "POST" and "clear_chat" in request.POST:
        ChatMessage.objects.all().delete()
        return redirect("chatbot")

    # PDF Upload and Processing
    if request.method == "POST" and request.FILES.get("file"):
        document_form = DocumentForm(request.POST, request.FILES)

        if document_form.is_valid():
            # Save document to database
            document = document_form.save()
            
            try:
                # Extract text from PDF
                pdf_path = document.file.path
                text = extract_text_from_pdf(pdf_path)
                
                # Chunk the text
                chunks = chunk_text(text, chunk_size=500)
                
                # Store chunks with embeddings in ChromaDB
                chunk_count = store_document_chunks(document.id, chunks)
                document.is_processed = True
                document.save()
                
                messages.success(
                    request,
                    f"Document uploaded! ({chunk_count} chunks indexed)"
                )
            
            except Exception as e:
                messages.error(request, f"Error processing PDF: {str(e)}")
                document.delete()

        return redirect("chatbot")

    # Chat Message with RAG
    if request.method == "POST" and request.POST.get("message"):
        user_message = request.POST.get("message")
        
        # Get the most recent processed document
        documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")
        
        if not documents.exists():
            response_text = "Please upload a PDF document first to start chatting."
        else:
            active_document = documents.first()
            
            # RAG Flow: Retrieve context -> Build prompt -> Get grounded answer
            response_text = get_rag_response(active_document.id, user_message)
        
        # Save chat message
        ChatMessage.objects.create(
            user_message=user_message,
            ai_response=response_text,
            document=active_document
        )

    # Fetch all chat messages
    chat_messages = ChatMessage.objects.order_by("-created_at")
    
    # Get the most recent processed document for context
    documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")
    active_document = documents.first() if documents.exists() else None

    return render(
        request,
        "chat/chat.html",
        {
            "response": response_text,
            "messages": chat_messages,
            "document_form": DocumentForm(),
            "active_document": active_document,
            "documents": documents,
        }
    )