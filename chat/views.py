from django.shortcuts import render, redirect
from django.contrib import messages
from django.conf import settings
from django.http import StreamingHttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt

from .models import ChatMessage, Document
from .forms import DocumentForm
from .pdf_utils import extract_text_from_pdf, chunk_text
from .rag_utils import (
    store_document_chunks,
    get_rag_response,
    stream_llm_response,
    delete_document_collection,
)

# Maximum number of message pairs to retain per session
_MAX_HISTORY = 15


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_or_create_session(request) -> str:
    """Ensure a session exists and return its key."""
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _build_conversation_history(session_key: str, max_pairs: int = _MAX_HISTORY) -> list:
    """Return a flat list of {role, content} dicts for the most recent *max_pairs* exchanges."""
    qs = (
        ChatMessage.objects
        .filter(session_key=session_key)
        .order_by("-created_at")
        .only("user_message", "ai_response")[:max_pairs]
    )
    history: list[dict] = []
    for cm in reversed(list(qs)):
        history.append({"role": "user", "content": cm.user_message})
        history.append({"role": "assistant", "content": cm.ai_response})
    return history


def _trim_history(session_key: str, max_pairs: int = _MAX_HISTORY) -> None:
    """Delete the oldest messages beyond *max_pairs* for this session in one query."""
    keep_ids = list(
        ChatMessage.objects
        .filter(session_key=session_key)
        .order_by("-created_at")
        .values_list("id", flat=True)[:max_pairs]
    )
    ChatMessage.objects.filter(session_key=session_key).exclude(id__in=keep_ids).delete()


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def chatbot(request):
    """Handle PDF upload, document management, and page rendering.

    Chat messages are sent exclusively via the ``stream_chat`` AJAX endpoint;
    this view only serves the page shell and handles form actions.
    """
    session_key = _get_or_create_session(request)

    if request.method == "POST":
        # ---- Clear all history and documents ----
        if "clear_chat" in request.POST:
            ChatMessage.objects.filter(session_key=session_key).delete()
            for doc in Document.objects.filter(is_processed=True):
                try:
                    delete_document_collection(doc.id)
                except Exception:
                    pass
            Document.objects.filter(is_processed=True).delete()
            request.session.flush()
            messages.success(request, "Chat history and active document cleared.")
            return redirect("chatbot")

        # ---- Remove the active document ----
        if "remove_document" in request.POST:
            doc = Document.objects.filter(is_processed=True).order_by("-uploaded_at").first()
            if doc:
                try:
                    doc.is_processed = False
                    doc.save()
                    delete_document_collection(doc.id)
                    messages.success(request, "Active document removed.")
                except Exception as exc:
                    messages.error(request, f"Error removing document: {exc}")
            return redirect("chatbot")

        # ---- PDF upload ----
        if request.FILES.get("file"):
            form = DocumentForm(request.POST, request.FILES)
            if form.is_valid():
                document = form.save()
                try:
                    text = extract_text_from_pdf(document.file.path)
                    if not text.strip():
                        raise ValueError("No readable text found in this PDF.")
                    chunks = chunk_text(text, chunk_size=500)
                    chunk_count = store_document_chunks(document.id, chunks)
                    document.is_processed = True
                    document.save()
                    messages.success(request, f"Document uploaded! ({chunk_count} chunks indexed)")
                except Exception as exc:
                    messages.error(request, f"Error processing PDF: {exc}")
                    document.delete()
            return redirect("chatbot")

    # ---- GET: render page ----
    chat_messages = (
        ChatMessage.objects
        .filter(session_key=session_key)
        .order_by("-created_at")
        .only("user_message", "ai_response", "created_at")
    )
    active_document = Document.objects.filter(is_processed=True).order_by("-uploaded_at").first()

    return render(
        request,
        "chat/chat.html",
        {
            "chat_messages": chat_messages,
            "document_form": DocumentForm(),
            "active_document": active_document,
        },
    )


@csrf_exempt
def stream_chat(request):
    """AJAX endpoint: stream the LLM reply for a user message.

    POST params:
        message      – the user's text (required)
        no_document  – "on" / "true" / "1" to bypass the active document

    Behaviour:
        - Active document present and *not* bypassed → RAG response (single chunk).
        - No document or bypassed → streaming LLM response (chunked).
    """
    if request.method != "POST":
        return HttpResponseBadRequest("POST required")

    user_message = (request.POST.get("message") or "").strip()
    if not user_message:
        return HttpResponseBadRequest("Missing message")

    bypass = request.POST.get("no_document") in ("on", "true", "1")
    session_key = _get_or_create_session(request)

    active_document = Document.objects.filter(is_processed=True).order_by("-uploaded_at").first()

    # ---- RAG path ----
    if active_document and not bypass:
        history = _build_conversation_history(session_key)
        try:
            resp_text = get_rag_response(
                active_document.id,
                user_message,
                conversation_history=history or None,
            )
        except Exception as exc:
            resp_text = f"Error generating response: {exc}"

        ChatMessage.objects.create(
            user_message=user_message,
            ai_response=resp_text,
            document=active_document,
            session_key=session_key,
        )
        _trim_history(session_key)
        return StreamingHttpResponse((resp_text,), content_type="text/plain")

    # ---- Simple streaming LLM path ----
    # Use only the last 2 pairs (4 messages) to keep prompts small and fast
    history = _build_conversation_history(session_key, max_pairs=2)
    model_name = getattr(settings, "FAST_OLLAMA_MODEL", None)

    def stream_generator():
        buffer: list[str] = []
        try:
            for piece in stream_llm_response(user_message, conversation_history=history or None, model_name=model_name):
                buffer.append(piece)
                yield piece
        except GeneratorExit:
            return
        finally:
            final_text = "".join(buffer).strip()
            if final_text:
                try:
                    ChatMessage.objects.create(
                        user_message=user_message,
                        ai_response=final_text,
                        document=None,
                        session_key=session_key,
                    )
                    _trim_history(session_key)
                except Exception:
                    pass

    return StreamingHttpResponse(stream_generator(), content_type="text/plain")