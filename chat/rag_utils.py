"""
RAG (Retrieval-Augmented Generation) utilities for chatbot.

Handles:
- Query embedding conversion
- Semantic retrieval from ChromaDB
- RAG prompt building
- Ollama integration for grounded answers
"""

import os
import shutil
import chromadb
from .embedding_utils import model
from django.conf import settings

# ---------------------------------------------------------------------------
# Ollama client initialisation
# ---------------------------------------------------------------------------
# Try to import the top-level `chat` function (ollama >= 0.2).
# Fall back to instantiating an Ollama client for older versions.
# If neither works, _ollama_chat stays None and callers return a clear error.
_ollama_chat = None
try:
    from ollama import chat as _ollama_chat  # noqa: F401
except Exception:
    try:
        from ollama import Ollama as _OllamaClass

        _ollama_client = _OllamaClass()

        def _ollama_chat(*args, **kwargs):  # type: ignore[misc]
            return _ollama_client.chat(*args, **kwargs)

    except Exception:
        _ollama_chat = None

# ---------------------------------------------------------------------------
# ChromaDB persistent client
# ---------------------------------------------------------------------------
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
os.makedirs(DB_DIR, exist_ok=True)
_chroma_client = chromadb.PersistentClient(path=DB_DIR)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_content(response) -> str:
    """Normalise an Ollama response (object / dict / str) to a plain string."""
    if isinstance(response, str):
        return response.strip()
    if isinstance(response, dict):
        msg = response.get("message")
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"]).strip()
        if "content" in response:
            return str(response["content"]).strip()
    if hasattr(response, "message"):
        msg = getattr(response, "message")
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"]).strip()
        if hasattr(msg, "content"):
            return str(getattr(msg, "content")).strip()
    if hasattr(response, "content"):
        return str(getattr(response, "content")).strip()
    if hasattr(response, "text"):
        return str(getattr(response, "text")).strip()
    return str(response).strip()


def _extract_chunk_content(chunk) -> str | None:
    """Extract the text delta from a streaming chunk, or None if empty."""
    if isinstance(chunk, str):
        return chunk or None
    if isinstance(chunk, dict):
        # OpenAI-style delta
        delta = chunk.get("delta")
        if isinstance(delta, dict) and "content" in delta:
            return str(delta["content"]) or None
        # Ollama message shape
        msg = chunk.get("message")
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"]) or None
        if "content" in chunk:
            return str(chunk["content"]) or None
    # Object-like (e.g. ollama._types.ChatResponse)
    if hasattr(chunk, "message"):
        msg = getattr(chunk, "message")
        if isinstance(msg, dict) and "content" in msg:
            return str(msg["content"]) or None
        if hasattr(msg, "content"):
            val = str(getattr(msg, "content"))
            return val or None
    if hasattr(chunk, "content"):
        val = str(getattr(chunk, "content"))
        return val or None
    return None


def _get_chroma_collection(doc_id: int):
    """Return (or create) the ChromaDB collection for *doc_id*.

    On a schema-mismatch error (stale SQLite file), the database is wiped and
    re-initialised transparently.
    """
    global _chroma_client  # noqa: PLW0603
    collection_name = f"doc_{doc_id}"
    try:
        return _chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as exc:
        msg = str(exc).lower()
        if any(kw in msg for kw in ("no such column", "collections.topic", "database disk image is malformed")):
            # Wipe stale DB files and recreate the client
            for entry in os.listdir(DB_DIR):
                full = os.path.join(DB_DIR, entry)
                try:
                    shutil.rmtree(full) if os.path.isdir(full) else os.remove(full)
                except Exception:
                    pass
            _chroma_client = chromadb.PersistentClient(path=DB_DIR)
            return _chroma_client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )
        raise


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def store_document_chunks(doc_id: int, chunks: list[str]) -> int:
    """Store *chunks* with embeddings in the ChromaDB collection for *doc_id*.

    Returns the number of chunks stored.
    """
    if not chunks:
        return 0
    collection = _get_chroma_collection(doc_id)
    embeddings = model.encode(chunks).tolist()
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": str(doc_id), "chunk_index": i} for i in range(len(chunks))]
    collection.add(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=chunks)
    return len(chunks)


def retrieve_relevant_chunks(doc_id: int, query: str, top_k: int = 3) -> list[str]:
    """Return the *top_k* most semantically similar chunks for *query*."""
    try:
        collection = _get_chroma_collection(doc_id)
        query_embedding = model.encode([query]).tolist()[0]
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        if results and results.get("documents"):
            return results["documents"][0]
        return []
    except Exception:
        return []


def build_rag_prompt(question: str, chunks: list[str]) -> str:
    """Construct a RAG prompt from *question* and retrieved *chunks*."""
    context = "\n\n".join(chunks)
    return (
        "You are answering questions about a document.\n\n"
        f"Document Content:\n{context}\n\n"
        f"User Question:\n{question}\n\n"
        "Rules:\n"
        '1. Answer ONLY using information from the document content.\n'
        "2. If the answer exists in the document, provide it clearly.\n"
        "3. Summarize relevant information when appropriate.\n"
        '4. Do NOT say "information not found" unless the document truly contains no relevant information.\n'
        "5. Keep the answer concise but complete.\n\n"
        "Answer:"
    )


def get_rag_response(
    doc_id: int,
    user_question: str,
    conversation_history: list | None = None,
    model_name: str | None = None,
) -> str:
    """Return a grounded answer from Ollama via RAG.

    Flow: retrieve chunks → build prompt → call Ollama → return text.
    """
    if _ollama_chat is None:
        return "Ollama client is not available. Install the `ollama` package."

    chunks = retrieve_relevant_chunks(doc_id, user_question)
    if not chunks:
        return "No relevant information found in the uploaded document. Please check your PDF content."

    rag_prompt = build_rag_prompt(user_question, chunks)
    # Include at most the last 1 exchange (2 messages) for context efficiency
    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history[-2:])
    messages.append({"role": "user", "content": rag_prompt})

    try:
        _model = model_name or getattr(settings, "DEFAULT_OLLAMA_MODEL", "gemma3:4b")
        response = _ollama_chat(model=_model, messages=messages)
        return _extract_content(response)
    except Exception as exc:
        return f"Error generating response: {exc}"


def stream_llm_response(
    user_question: str,
    conversation_history: list | None = None,
    model_name: str | None = None,
):
    """Yield LLM response text chunks as they stream from Ollama.

    Falls back to a single non-streaming call if the client doesn't support
    the *stream* keyword argument.
    """
    if _ollama_chat is None:
        yield "Ollama client is not available. Install the `ollama` package."
        return

    _model = model_name or getattr(settings, "DEFAULT_OLLAMA_MODEL", "gemma3:4b")
    messages: list[dict] = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_question})

    try:
        try:
            response_iter = _ollama_chat(model=_model, messages=messages, stream=True)
        except TypeError:
            # Client doesn't accept the stream kwarg — fall back to one-shot
            response_iter = None

        if response_iter is None:
            yield _extract_content(_ollama_chat(model=_model, messages=messages))
            return

        for chunk in response_iter:
            text = _extract_chunk_content(chunk)
            if text:
                yield text

    except Exception as exc:
        yield f"Error streaming response: {exc}"


def delete_document_collection(doc_id: int) -> None:
    """Delete the ChromaDB collection for *doc_id* (best-effort)."""
    try:
        _chroma_client.delete_collection(name=f"doc_{doc_id}")
    except Exception:
        pass
