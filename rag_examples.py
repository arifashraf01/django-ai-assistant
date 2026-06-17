"""
RAG Usage Examples - Helper Script

Shows different ways to use the RAG pipeline for testing and development.
Run from Django shell: python manage.py shell < rag_examples.py
"""

# Example 1: Store document chunks programmatically
# ================================================

from chat.models import Document
from chat.pdf_utils import extract_text_from_pdf, chunk_text
from chat.rag_utils import store_document_chunks, get_rag_response

def store_pdf_in_chromadb(document_id):
    """
    Helper to process an already-uploaded document and store in ChromaDB.
    
    Usage:
        doc = Document.objects.last()
        store_pdf_in_chromadb(doc.id)
    """
    doc = Document.objects.get(id=document_id)
    
    # Extract and chunk
    text = extract_text_from_pdf(doc.file.path)
    chunks = chunk_text(text, chunk_size=500)
    
    # Store in ChromaDB
    chunk_count = store_document_chunks(doc.id, chunks)
    
    # Mark as processed
    doc.is_processed = True
    doc.save()
    
    print(f"✓ Stored {chunk_count} chunks for document {document_id}")
    return chunk_count


# Example 2: Get RAG response for a query
# ========================================

def ask_about_document(document_id, question):
    """
    Get a RAG-based answer about a specific document.
    
    Usage:
        response = ask_about_document(1, "What is this about?")
        print(response)
    """
    response = get_rag_response(document_id, question)
    return response


# Example 3: Retrieve and inspect chunks
# =======================================

from chat.rag_utils import retrieve_relevant_chunks

def inspect_retrieval(document_id, query, top_k=3):
    """
    Inspect which chunks are retrieved for a query.
    Useful for debugging retrieval quality.
    
    Usage:
        inspect_retrieval(1, "What is AWS?")
    """
    chunks = retrieve_relevant_chunks(document_id, query, top_k=top_k)
    
    print(f"\nQuery: '{query}'")
    print(f"Retrieved {len(chunks)} chunks:\n")
    
    for i, chunk in enumerate(chunks, 1):
        print(f"[Chunk {i}]")
        print(f"{chunk}")
        print("-" * 60)
    
    return chunks


# Example 4: Batch process multiple PDFs
# =======================================

def process_all_documents():
    """
    Process all unprocessed documents in the database.
    
    Usage:
        process_all_documents()
    """
    unprocessed = Document.objects.filter(is_processed=False)
    
    for doc in unprocessed:
        try:
            count = store_pdf_in_chromadb(doc.id)
            print(f"✓ Processed {doc.file.name}: {count} chunks")
        except Exception as e:
            print(f"✗ Error processing {doc.file.name}: {e}")


# Example 5: Multi-turn conversation simulation
# =============================================

def multi_turn_chat(document_id, questions):
    """
    Simulate a multi-turn conversation about a document.
    
    Usage:
        questions = [
            "What is this document about?",
            "What are the main points?",
            "Can you summarize?"
        ]
        multi_turn_chat(1, questions)
    """
    from chat.models import ChatMessage
    
    print(f"\n{'='*60}")
    print(f"Multi-Turn Chat (Document {document_id})")
    print(f"{'='*60}\n")
    
    for i, question in enumerate(questions, 1):
        print(f"Q{i}: {question}")
        response = get_rag_response(document_id, question)
        print(f"A{i}: {response}\n")
        print("-" * 60 + "\n")
        
        # Save to database (optional)
        ChatMessage.objects.create(
            user_message=question,
            ai_response=response,
            document_id=document_id
        )


# Example 6: Compare different chunk sizes
# =========================================

from chat.rag_utils import create_embeddings

def test_chunk_sizes(pdf_path):
    """
    Test how different chunk sizes affect retrieval.
    
    Usage:
        test_chunk_sizes("media/documents/sample.pdf")
    """
    from chat.pdf_utils import extract_text_from_pdf, chunk_text
    
    text = extract_text_from_pdf(pdf_path)
    
    chunk_sizes = [250, 500, 1000]
    
    print(f"\nTesting chunk sizes for: {pdf_path}")
    print("-" * 60)
    
    for size in chunk_sizes:
        chunks = chunk_text(text, chunk_size=size)
        embeddings = create_embeddings(chunks)
        
        avg_chunk_words = sum(len(c.split()) for c in chunks) / len(chunks)
        total_tokens = len(embeddings) * 384  # 384-dim vectors
        
        print(f"\nChunk Size: {size} chars")
        print(f"  Number of chunks: {len(chunks)}")
        print(f"  Avg chunk (words): {avg_chunk_words:.1f}")
        print(f"  Total vector storage: {total_tokens:,} floats")


# Example 7: Document statistics and health check
# ================================================

def document_stats():
    """
    Get statistics about stored documents.
    
    Usage:
        document_stats()
    """
    from chat.models import ChatMessage, Document
    from django.db.models import Count, Q
    
    docs = Document.objects.annotate(
        message_count=Count('chat_messages', filter=Q(chat_messages__isnull=False))
    )
    
    print(f"\n{'='*60}")
    print("Document Statistics")
    print(f"{'='*60}\n")
    
    for doc in docs:
        status = "✓ Processed" if doc.is_processed else "✗ Not Processed"
        print(f"Document: {doc.file.name}")
        print(f"  Status: {status}")
        print(f"  Uploaded: {doc.uploaded_at}")
        print(f"  Chat messages: {doc.message_count}")
        print()


# ============================================================
# QUICK START - Uncomment one of the examples below to test
# ============================================================

if __name__ == "__main__":
    # Get the most recent document
    from chat.models import Document
    
    doc = Document.objects.all().order_by('-uploaded_at').first()
    
    if doc:
        doc_id = doc.id
        
        # Uncomment one to test:
        
        # Example 1: Store chunks (if not already processed)
        # store_pdf_in_chromadb(doc_id)
        
        # Example 2: Ask a question
        # response = ask_about_document(doc_id, "What is this document about?")
        # print(response)
        
        # Example 3: Inspect retrieval
        # inspect_retrieval(doc_id, "What are the key topics?")
        
        # Example 4: Process all documents
        # process_all_documents()
        
        # Example 5: Multi-turn conversation
        # questions = [
        #     "What is this document about?",
        #     "What are the main topics?",
        #     "Can you summarize the key points?"
        # ]
        # multi_turn_chat(doc_id, questions)
        
        # Example 7: Document statistics
        # document_stats()
        
        print("✓ RAG examples ready. Uncomment an example to test!")
    else:
        print("No documents found. Please upload a PDF first.")
