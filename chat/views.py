from django.shortcuts import render, redirect
from django.contrib import messages
from .models import ChatMessage, Document
from .forms import DocumentForm
from .pdf_utils import extract_text_from_pdf, chunk_text
from .rag_utils import store_document_chunks, get_rag_response, get_llm_response, delete_document_collection
from .rag_utils import stream_llm_response
from django.http import StreamingHttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt


def chatbot(request):
    """
    Main chatbot view handling:
    - PDF upload and processing
    - RAG-based chat with context from uploaded PDFs
    - Chat history management
    """
    
    response_text = ""
    active_document = None

    # Ensure the session exists so we can scope chat history
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    # Clear chat history for this session
    if request.method == "POST" and "clear_chat" in request.POST:

         # Delete chat history
        ChatMessage.objects.filter(session_key=session_key).delete()

         # Remove active document
        documents = Document.objects.filter(is_processed=True)

        for doc in documents:
           try:
            delete_document_collection(doc.id)
           except Exception:
            pass

        documents.delete()

        # Clear session
        request.session.flush()

        messages.success(request, "Chat history and active document cleared.")

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

        # Build conversation history from this session (last 15 pairs)
        history_qs = ChatMessage.objects.filter(session_key=session_key).order_by("-created_at")[:15]
        conversation_history = []
        for cm in reversed(list(history_qs)):
            conversation_history.append({"role": "user", "content": cm.user_message})
            conversation_history.append({"role": "assistant", "content": cm.ai_response})

        # Get the most recent processed document
        documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")

        if documents.exists() and not bypass:
            active_document = documents.first()
            # RAG Flow: pass conversation history + document context
            response_text = get_rag_response(
                active_document.id,
                user_message,
                conversation_history=conversation_history if conversation_history else None,
            )
        else:
            # No active document or user chose to bypass -> direct agent response
            # For simple chat without a document, only send a small recent history
            # to the LLM (e.g., last 2 pairs) to keep prompts small and responses fast.
            if conversation_history:
                # conversation_history is ordered oldest->newest; take last 4 entries
                short_history = conversation_history[-4:]
            else:
                short_history = None

            from django.conf import settings as djsettings
            response_text = get_llm_response(
                user_message,
                conversation_history=short_history,
                model_name=getattr(djsettings, "FAST_OLLAMA_MODEL", None),
            )
            # when bypassing or no doc present, don't associate message with a document
            active_document = None

        # Save chat message scoped to this session
        ChatMessage.objects.create(
            user_message=user_message,
            ai_response=response_text,
            document=active_document,
            session_key=session_key,
        )

        # Trim history to last 15 pairs for this session
        total = ChatMessage.objects.filter(session_key=session_key).count()
        if total > 15:
            extra = total - 15
            old_qs = ChatMessage.objects.filter(session_key=session_key).order_by("created_at")[:extra]
            # bulk delete
            ids_to_delete = [o.id for o in old_qs]
            ChatMessage.objects.filter(id__in=ids_to_delete).delete()

    # Fetch only session-scoped chat messages
    chat_messages = ChatMessage.objects.filter(session_key=session_key).order_by("-created_at")
    
    # Get the most recent processed document for context
    documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")
    active_document = documents.first() if documents.exists() else None

    return render(
        request,
        "chat/chat.html",
        {
            "response": response_text,
            "chat_messages": chat_messages,
            "document_form": DocumentForm(),
            "active_document": active_document,
            "documents": documents,
        }
    )


@csrf_exempt
def stream_chat(request):
    """Stream chat responses for simple (no-PDF) conversations.

    Accepts POST with 'message' and optional 'no_document'. Streams text chunks
    (plain text) as they arrive from the model. If a document is active and
    not bypassed, falls back to synchronous RAG response (single chunk).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    user_message = request.POST.get("message")
    if not user_message:
        return HttpResponseBadRequest("Missing message")

    bypass = True if request.POST.get("no_document") in ["on", "true", "1"] else False

    # session
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key

    # Build short history for speed
    history_qs = ChatMessage.objects.filter(session_key=session_key).order_by("-created_at")[:15]
    conversation_history = []
    for cm in reversed(list(history_qs)):
        conversation_history.append({"role": "user", "content": cm.user_message})
        conversation_history.append({"role": "assistant", "content": cm.ai_response})

    # Check for active document
    documents = Document.objects.filter(is_processed=True).order_by("-uploaded_at")
    if documents.exists() and not bypass:
        # For RAG we don't stream here; return a single response and let client handle it
        active_document = documents.first()
        resp_text = get_rag_response(active_document.id, user_message, conversation_history=conversation_history if conversation_history else None)

        # Save message and return as single chunk
        ChatMessage.objects.create(user_message=user_message, ai_response=resp_text, document=active_document, session_key=session_key)

        return StreamingHttpResponse((resp_text,), content_type='text/plain')

    # No document: stream from LLM using FAST_OLLAMA_MODEL
    from django.conf import settings as djsettings
    model_name = getattr(djsettings, 'FAST_OLLAMA_MODEL', None)

    def stream_generator():
        buffer = []
        try:
            for piece in stream_llm_response(user_message, conversation_history=conversation_history if conversation_history else None, model_name=model_name):
                text = piece if isinstance(piece, str) else str(piece)
                buffer.append(text)
                yield text
        except GeneratorExit:
            return
        finally:
            # After streaming completes, persist the final assistant response
            try:
                final_text = ''.join(buffer).strip()
                if final_text:
                    ChatMessage.objects.create(user_message=user_message, ai_response=final_text, document=None, session_key=session_key)
            except Exception:
                pass

    # Save a placeholder chat message will be updated after completion (optional)
    # We'll append final response after streaming completes on client side

    return StreamingHttpResponse(stream_generator(), content_type='text/plain')