"""
RAG Pipeline Test Script

Demonstrates the complete RAG workflow:
1. Extract text from PDF
2. Chunk text
3. Generate embeddings
4. Store in ChromaDB
5. Retrieve relevant chunks
6. Build RAG prompt
7. Get response from Ollama
"""

from chat.pdf_utils import extract_text_from_pdf, chunk_text
from chat.embedding_utils import model, create_embeddings
from chat.rag_utils import (
    store_document_chunks,
    retrieve_relevant_chunks,
    build_rag_prompt,
    get_or_create_collection
)

# Example PDF path
PDF_PATH = "media/documents/arif_resume.pdf"
DOC_ID = 1  # Using doc_id 1 for this test

def test_rag_pipeline():
    """Test the complete RAG pipeline."""
    
    print("=" * 60)
    print("RAG PIPELINE TEST")
    print("=" * 60)
    
    # Step 1: Extract text
    print("\n[1] Extracting text from PDF...")
    text = extract_text_from_pdf(PDF_PATH)
    print(f"   ✓ Extracted {len(text)} characters")
    
    # Step 2: Chunk text
    print("\n[2] Chunking text...")
    chunks = chunk_text(text, chunk_size=500)
    print(f"   ✓ Created {len(chunks)} chunks")
    print(f"   Sample chunk (first 100 chars): {chunks[0][:100]}...")
    
    # Step 3: Generate embeddings
    print("\n[3] Generating embeddings...")
    embeddings = create_embeddings(chunks)
    print(f"   ✓ Created {len(embeddings)} embeddings")
    print(f"   ✓ Vector dimension: {len(embeddings[0])}")
    
    # Step 4: Store in ChromaDB
    print("\n[4] Storing chunks in ChromaDB...")
    chunk_count = store_document_chunks(DOC_ID, chunks)
    print(f"   ✓ Stored {chunk_count} chunks")
    
    # Step 5: Test retrieval
    print("\n[5] Testing semantic retrieval...")
    
    test_queries = [
        "What is this document about?",
        "What are the main skills?",
        "When was this written?"
    ]
    
    for query in test_queries:
        print(f"\n   Query: '{query}'")
        retrieved = retrieve_relevant_chunks(DOC_ID, query, top_k=2)
        print(f"   ✓ Retrieved {len(retrieved)} chunks:")
        for i, chunk in enumerate(retrieved, 1):
            print(f"      [{i}] {chunk[:100]}...")
    
    # Step 6: Build RAG prompt
    print("\n[6] Building RAG prompt...")
    query = "What skills are mentioned?"
    chunks = retrieve_relevant_chunks(DOC_ID, query, top_k=3)
    prompt = build_rag_prompt(query, chunks)
    print(f"   ✓ Prompt length: {len(prompt)} characters")
    print("\n   RAG Prompt Preview:")
    print("   " + "-" * 50)
    print("   " + prompt[:300] + "...")
    print("   " + "-" * 50)
    
    print("\n[7] To get Ollama response, use:")
    print("   from chat.rag_utils import get_rag_response")
    print(f"   response = get_rag_response({DOC_ID}, '{query}')")
    
    print("\n" + "=" * 60)
    print("RAG PIPELINE TEST COMPLETED")
    print("=" * 60)


if __name__ == "__main__":
    test_rag_pipeline()
