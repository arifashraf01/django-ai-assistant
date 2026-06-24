"""
RAG (Retrieval-Augmented Generation) utilities for chatbot.

Handles:
- Query embedding conversion
- Semantic retrieval from ChromaDB
- RAG prompt building
- Ollama integration for grounded answers
"""

import os
import chromadb
from .embedding_utils import model
from django.conf import settings
import shutil
import glob

# Ollama client compatibility wrapper: different versions expose different APIs.
# Try to import the top-level `chat` function, otherwise instantiate an Ollama
# client and wrap its `chat` method. If neither is available, set to None so
# callers can return a clear error.
_ollama_chat = None
try:
    from ollama import chat as _chat_func
    _ollama_chat = _chat_func
except Exception:
    try:
        from ollama import Ollama

        _ollama_client = Ollama()

        def _chat_func(*args, **kwargs):
            return _ollama_client.chat(*args, **kwargs)

        _ollama_chat = _chat_func
    except Exception:
        _ollama_chat = None

# Initialize ChromaDB client and collection
DB_DIR = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
os.makedirs(DB_DIR, exist_ok=True)

client = chromadb.PersistentClient(path=DB_DIR)


def get_or_create_collection(doc_id):
    """
    Get or create a ChromaDB collection for a specific document.
    
    Each uploaded PDF gets its own collection to maintain separation.
    """
    collection_name = f"doc_{doc_id}"

    try:
        return client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    except Exception as e:
        # Detect common SQLite schema mismatch errors from an old/corrupt
        # ChromaDB sqlite file (e.g., "no such column: collections.topic").
        msg = str(e).lower()
        if "no such column" in msg or "collections.topic" in msg or "database disk image is malformed" in msg:
            print(f"ChromaDB schema error detected: {e}; attempting to reset chroma DB at {DB_DIR}")
            try:
                # Remove existing chroma_db files so ChromaDB can recreate schema
                for path in glob.glob(os.path.join(DB_DIR, "*")):
                    try:
                        if os.path.isdir(path):
                            shutil.rmtree(path)
                        else:
                            os.remove(path)
                    except Exception:
                        pass

                # Recreate client and retry
                globals()['client'] = chromadb.PersistentClient(path=DB_DIR)
                return client.get_or_create_collection(
                    name=collection_name,
                    metadata={"hnsw:space": "cosine"}
                )
            except Exception as e2:
                print(f"Failed to reset ChromaDB: {e2}")
                raise

        # otherwise, re-raise the original exception
        raise


def store_document_chunks(doc_id, chunks):
    """
    Store document chunks with embeddings in ChromaDB.
    
    Args:
        doc_id: Document ID from Django model
        chunks: List of text chunks to store
    
    Returns:
        Number of chunks stored
    """
    if not chunks:
        return 0
    
    collection = get_or_create_collection(doc_id)
    
    # Generate embeddings for all chunks
    embeddings = model.encode(chunks).tolist()
    
    # Store in ChromaDB with metadata
    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"doc_id": str(doc_id), "chunk_index": i} for i in range(len(chunks))]
    print(f"INDEXING DOC ID: {doc_id}")
    print(f"COLLECTION NAME: doc_{doc_id}")
    print(f"CHUNKS STORED: {len(chunks)}")
    collection.add(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=chunks
    )
    
    return len(chunks)


def retrieve_relevant_chunks(doc_id, query, top_k=3):
    """
    Retrieve top-k most relevant chunks for a query using semantic similarity.
    
    Args:
        doc_id: Document ID to search within
        query: User's question
        top_k: Number of chunks to retrieve (default 3)
    
    Returns:
        List of relevant chunk texts
    """
    try:
        collection = get_or_create_collection(doc_id)
        
        # Convert query to embedding
        query_embedding = model.encode([query]).tolist()[0]
      
        # Search ChromaDB for similar chunks
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k, 5)  # Retrieve up to 5, return top_k
        )
      
        # Extract and return chunk texts
        if results and results["documents"]:
            return results["documents"][0]  # Return first (and only) query's results
        
        return []
    
    except Exception as e:
        print(f"Error retrieving chunks: {e}")
        return []

def build_rag_prompt(question, chunks):
    """
    Build a RAG prompt with retrieved context and user question.
    """
    context = "\n\n".join(chunks)

    prompt = f"""
You are answering questions about a document.

Document Content:
{context}

User Question:
{question}

Rules:
1. Answer ONLY using information from the document content.
2. If the answer exists in the document, provide it clearly.
3. Summarize relevant information when appropriate.
4. Do NOT say "information not found" unless the document truly contains no relevant information.
5. Keep the answer concise but complete.

Answer:
"""

    return prompt


def get_rag_response(doc_id, user_question, conversation_history=None, model_name=None):
    """
    Get a grounded answer from Ollama using RAG.
    
    Flow:
    1. Retrieve relevant chunks from ChromaDB
    2. Build RAG prompt
    3. Send to Ollama Gemma3:4b
    4. Return grounded answer
    
    Args:
        doc_id: Document ID to retrieve context from
        user_question: User's question
    
    Returns:
        Response from Ollama
    """
    # Step 1: Retrieve relevant chunks
    chunks = retrieve_relevant_chunks(doc_id, user_question, top_k=3)
    
    if not chunks:
        return "No relevant information found in the uploaded document. Please check your PDF content."
    
    # Step 2: Build RAG prompt
    rag_prompt = build_rag_prompt(user_question, chunks)

    # Build messages for the chat API. We include prior conversation messages
    # (if any) so the model has the full turn history. Then we inject the
    # document context as a system message before the current user question.
    messages = []

    if conversation_history:
        messages.extend(conversation_history[-2:])  # keep recent context only

    messages.append({
    "role": "user",
    "content": rag_prompt 
    })

    # Step 3 & 4: Send to Ollama and return response
    if _ollama_chat is None:
        return "Ollama client is not available. Install the `ollama` package."

    try:
        _model = model_name or getattr(settings, "DEFAULT_OLLAMA_MODEL", "gemma3:4b")
        response = _ollama_chat(
            model=_model,
            messages=messages
        )
        print("OLLAMA RAW RESPONSE:", response)
        # Normalize response shapes across ollama versions and return only the
        # assistant content (trimmed). Handle dicts, simple strings, and
        # response objects that expose a `message` with `content`.
        if isinstance(response, str):
            return response.strip()

        if isinstance(response, dict):
            # Common shape: {"message": {"content": "..."}}
            if "message" in response and isinstance(response["message"], dict) and "content" in response["message"]:
                return str(response["message"]["content"]).strip()
            # Alternate shape: {"content": "..."}
            if "content" in response:
                return str(response["content"]).strip()

        # Object shapes: response.message may be an object with a .content attr
        if hasattr(response, "message"):
            msg = getattr(response, "message")
            if isinstance(msg, dict) and "content" in msg:
                return str(msg["content"]).strip()
            if hasattr(msg, "content"):
                return str(getattr(msg, "content")).strip()

        # Direct attributes on response
        if hasattr(response, "content"):
            return str(getattr(response, "content")).strip()
        if hasattr(response, "text"):
            return str(getattr(response, "text")).strip()

        # Fallback: string representation (trimmed)
        return str(response).strip()

    except Exception as e:
        return f"Error generating response: {str(e)}"


def delete_document_collection(doc_id):
    """
    Delete ChromaDB collection when document is removed.
    
    Args:
        doc_id: Document ID to delete
    """
    try:
        collection_name = f"doc_{doc_id}"
        client.delete_collection(name=collection_name)
    except Exception as e:
        print(f"Error deleting collection: {e}")


def get_llm_response(user_question, conversation_history=None, model_name=None):
    """
    Get a direct LLM response from Ollama without using any document context.

    Args:
        user_question: The user's question as a string

    Returns:
        Response text from the model
    """
    # Build messages list including conversation history so follow-ups work.
    messages = []
    if conversation_history:
        messages.extend(conversation_history)

    messages.append({"role": "user", "content": user_question})

    if _ollama_chat is None:
        return "Ollama client is not available. Install the `ollama` package."

    try:
        _model = model_name or getattr(settings, "DEFAULT_OLLAMA_MODEL", "gemma3:4b")
        response = _ollama_chat(
            model=_model,
            messages=messages
        )

        if isinstance(response, str):
            return response.strip()
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict) and "content" in response["message"]:
                return str(response["message"]["content"]).strip()
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
    except Exception as e:
        return f"Error generating response: {str(e)}"


def stream_llm_response(user_question, conversation_history=None, model_name=None):
    """
    Stream LLM response as an iterator of text chunks. Falls back to a single
    message if the client doesn't support streaming.
    """
    if _ollama_chat is None:
        yield "Ollama client is not available. Install the `ollama` package."
        return

    _model = model_name or getattr(settings, "DEFAULT_OLLAMA_MODEL", "gemma3:4b")

    messages = []
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_question})

    try:
        # Many clients support a `stream=True` flag that returns an iterator.
        response_iter = None
        try:
            response_iter = _ollama_chat(model=_model, messages=messages, stream=True)
        except TypeError:
            # client may not accept stream kwarg
            response_iter = None

        if response_iter is None:
            # No streaming support; produce a single response
            resp = _ollama_chat(model=_model, messages=messages)
            # reuse normalization logic
            text = None
            if isinstance(resp, str):
                text = resp.strip()
            elif isinstance(resp, dict):
                if "message" in resp and isinstance(resp["message"], dict) and "content" in resp["message"]:
                    text = str(resp["message"]["content"]).strip()
                elif "content" in resp:
                    text = str(resp["content"]).strip()
            elif hasattr(resp, "message"):
                msg = getattr(resp, "message")
                if isinstance(msg, dict) and "content" in msg:
                    text = str(msg["content"]).strip()
                elif hasattr(msg, "content"):
                    text = str(getattr(msg, "content")).strip()
            if text is None:
                text = str(resp).strip()

            yield text
            return

        # If we have an iterable response, yield chunks as they come
        for chunk in response_iter:
            # chunk may be dict/string/object; normalize minimally
            out = None
            if isinstance(chunk, str):
                out = chunk
            elif isinstance(chunk, dict):
                # some stream events include incremental content
                if "delta" in chunk and isinstance(chunk["delta"], dict) and "content" in chunk["delta"]:
                    out = str(chunk["delta"]["content"])
                elif "message" in chunk and isinstance(chunk["message"], dict) and "content" in chunk["message"]:
                    out = str(chunk["message"]["content"])
                elif "content" in chunk:
                    out = str(chunk["content"])
            else:
                # object-like responses (e.g., ollama._types.ChatResponse)
                if hasattr(chunk, "message"):
                    msg = getattr(chunk, "message")
                    if isinstance(msg, dict) and "content" in msg:
                        out = str(msg["content"])
                    elif hasattr(msg, "content"):
                        out = str(getattr(msg, "content"))
                elif hasattr(chunk, "content"):
                    out = str(getattr(chunk, "content"))

            if out:
                yield out

    except Exception as e:
        yield f"Error streaming response: {str(e)}"
