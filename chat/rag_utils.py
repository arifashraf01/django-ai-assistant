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
    return client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )


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
    
    Args:
        question: User's question
        chunks: Retrieved context chunks
    
    Returns:
        Formatted prompt for the LLM
    """
    context = "\n\n".join(chunks)
    
    prompt = f"""Based on the provided context, answer the user's question.

CONTEXT:
{context}

QUESTION:
{question}

INSTRUCTIONS:
- Answer only based on the provided context
- Be concise and direct
- If the answer is not in the context, say: "This information was not found in the uploaded document."
- Do not make up or use external knowledge"""
    
    return prompt


def get_rag_response(doc_id, user_question, conversation_history=None):
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
        # conversation_history should be a list of dicts: {role: 'user'|'assistant', content: '...'}
        messages.extend(conversation_history)

    # Add the retrieved document context as a system instruction so the model
    # treats it as grounding information. This follows the requirement to send:
    # 1) Conversation history
    # 2) Retrieved document context
    # 3) Current user question
    messages.append({
        "role": "system",
        "content": "DOCUMENT_CONTEXT:\n\n" + "\n\n".join(chunks) + "\n\nINSTRUCTIONS: Answer using ONLY the provided document context. If the answer is not present, say: 'This information was not found in the uploaded document.'"
    })

    # Finally add the current user question
    messages.append({"role": "user", "content": user_question})

    # Step 3 & 4: Send to Ollama and return response
    if _ollama_chat is None:
        return "Ollama client is not available. Install the `ollama` package."

    try:
        response = _ollama_chat(
            model="gemma3:4b",
            messages=messages
        )

        # Normalize response shapes across ollama versions
        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            # Common shape: {"message": {"content": "..."}}
            if "message" in response and isinstance(response["message"], dict) and "content" in response["message"]:
                return response["message"]["content"]
            # Alternate shape: {"content": "..."}
            if "content" in response:
                return response["content"]

        # Fallback to string representation
        return str(response)

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


def get_llm_response(user_question, conversation_history=None):
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
        response = _ollama_chat(
            model="gemma3:4b",
            messages=messages
        )

        if isinstance(response, str):
            return response
        if isinstance(response, dict):
            if "message" in response and isinstance(response["message"], dict) and "content" in response["message"]:
                return response["message"]["content"]
            if "content" in response:
                return response["content"]

        return str(response)
    except Exception as e:
        return f"Error generating response: {str(e)}"
