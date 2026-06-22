from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ChatMessage, Document
from .forms import DocumentForm
from .pdf_utils import extract_text_from_pdf, chunk_text
from .rag_utils import store_document_chunks, get_rag_response, get_llm_response, delete_document_collection


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

    # Remove active document (mark as not processed and delete chroma collection)
    if request.method == "POST" and "remove_document" in request.POST:
        documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")
        if documents.exists():
            doc = documents.first()
            try:
                # mark as not processed so it no longer acts as active
                doc.is_processed = False
                doc.save()
                # remove its chromadb collection
                delete_document_collection(doc.id)
                messages.success(request, "Active document removed.")
            except Exception as e:
                messages.error(request, f"Error removing document: {e}")
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

    # Chat Message handling: support sending without document and with RAG when a document exists
    if request.method == "POST" and request.POST.get("message"):
        user_message = request.POST.get("message")

        # Check if user requested to bypass document
        bypass = True if request.POST.get("no_document") in ["on", "true", "1"] else False

        # Get the most recent processed document
        documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")

        if documents.exists() and not bypass:
            active_document = documents.first()
            # RAG Flow: Retrieve context -> Build prompt -> Get grounded answer
            response_text = get_rag_response(active_document.id, user_message)
        else:
            # No active document or user chose to bypass -> direct agent response
            response_text = get_llm_response(user_message)
            # when bypassing or no doc present, don't associate message with a document
            active_document = None

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