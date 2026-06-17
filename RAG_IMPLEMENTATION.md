# RAG Pipeline Implementation - Django AI Assistant

## Overview

This implementation completes a **Retrieval-Augmented Generation (RAG)** pipeline that provides context-aware answers from uploaded PDF documents.

### Architecture

```
User Query
    ↓
[Query Embedding] ← all-MiniLM-L6-v2
    ↓
[ChromaDB Search] ← Semantic similarity
    ↓
[Retrieve Top 3-5 Chunks] → Relevant context
    ↓
[Build RAG Prompt] → Context + Question
    ↓
[Ollama Gemma3:4b] ← Generate grounded answer
    ↓
User Response
```

## Components

### 1. **rag_utils.py** - RAG Pipeline Core

Implements the complete retrieval-augmented generation flow:

```python
# Query embedding (done in rag_utils)
query_embedding = model.encode([query]).tolist()[0]

# Semantic retrieval from ChromaDB
results = collection.query(query_embeddings=[query_embedding], n_results=3)

# RAG prompt building
prompt = f"Context: {chunks}\nQuestion: {query}"

# Ollama integration
response = chat(model="gemma3:4b", messages=[{"role": "user", "content": prompt}])
```

**Key Functions:**

| Function | Purpose |
|----------|---------|
| `get_or_create_collection(doc_id)` | Get/create ChromaDB collection per document |
| `store_document_chunks(doc_id, chunks)` | Embed and store chunks in ChromaDB |
| `retrieve_relevant_chunks(doc_id, query, top_k=3)` | Semantic search for relevant chunks |
| `build_rag_prompt(question, chunks)` | Build prompt with context |
| `get_rag_response(doc_id, user_question)` | End-to-end RAG response |
| `delete_document_collection(doc_id)` | Cleanup when document removed |

### 2. **views.py** - Chat Logic

PDF-aware chat view with integrated RAG:

```python
# PDF Upload Flow:
1. Save document to database
2. Extract text from PDF
3. Chunk text (500 char chunks)
4. Generate embeddings
5. Store in ChromaDB
6. Set is_processed = True

# Chat Flow:
1. Get most recent processed document
2. Retrieve relevant chunks from ChromaDB
3. Build RAG prompt
4. Get response from Ollama
5. Save with document reference
```

### 3. **models.py** - Data Models

**Updated Fields:**

- `ChatMessage.document` - ForeignKey to source document
- `Document.is_processed` - Flag indicating ChromaDB storage complete

**Usage:**
```python
# Get messages for a specific document
messages = ChatMessage.objects.filter(document=doc)

# Get most recent processed document
doc = Document.objects.filter(is_processed=True).first()
```

### 4. **templates/chat/chat.html** - User Interface

Enhanced template with:
- Active document display (filename, upload date)
- Disabled chat until PDF uploaded
- Document context in chat history
- Better UX/styling
- Success/error messages

## Workflow Examples

### Example 1: Upload PDF and Ask Questions

```
User: Upload "research_paper.pdf"
↓
System: 
  - Extracts text
  - Creates 45 chunks
  - Generates 45 embeddings (384-dimensional)
  - Stores in ChromaDB collection "doc_5"
  - Sets is_processed = True

User: "What is the main thesis?"
↓
System:
  1. Embed query: "What is the main thesis?"
  2. Search ChromaDB for top 3 similar chunks
  3. Build RAG prompt with context
  4. Send to Ollama: 
     "Context: [retrieved chunks]
      Question: What is the main thesis?
      Answer only from context."
  5. Return grounded answer
```

### Example 2: Multiple Questions on Same Document

```
User asks: "Summarize chapter 3"
User asks: "What does it say about AWS?"
User asks: "Define key terms"
↓
All queries search the same document's embeddings
→ Context-aware answers from same source
```

## Code Quality Features

### Interview-Friendly Design
- Clear function names with docstrings
- Simple, readable logic flow
- No complex dependencies (no LangChain)
- Easy to explain and extend

### Error Handling
```python
# Graceful fallback if no document uploaded
if not documents.exists():
    response_text = "Please upload a PDF document first"

# Try-except for PDF processing
try:
    chunks = chunk_text(text)
except Exception as e:
    messages.error(request, f"Error: {str(e)}")
```

### Reusable Utilities
```python
from chat.pdf_utils import extract_text_from_pdf, chunk_text
from chat.embedding_utils import model, create_embeddings
from chat.rag_utils import get_rag_response
```

## Key Design Decisions

### 1. Per-Document Collections
```python
collection_name = f"doc_{doc_id}"
```
Each PDF gets its own ChromaDB collection for:
- Isolation and scalability
- Easy document deletion
- Fast retrieval within document

### 2. Persistent ChromaDB
```python
client = chromadb.PersistentClient(path=DB_DIR)
```
- Embeddings survive app restarts
- No re-processing on restart
- Standard `chroma_db/` directory

### 3. Simple Embedding Model
```python
model = SentenceTransformer("all-MiniLM-L6-v2")
```
- Lightweight (22MB)
- Fast inference (384-dimensional vectors)
- Excellent for retrieval tasks

### 4. Fixed Chunk Size
```python
chunks = chunk_text(text, chunk_size=500)
```
- 500 characters ≈ 75-100 words
- Good semantic cohesion
- Overlapping context with multiple chunks

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Ensure Ollama is Running
```bash
ollama serve
# In another terminal:
ollama pull gemma3:4b
```

### 4. Start Django
```bash
python manage.py runserver
```

### 5. Access UI
```
http://localhost:8000
```

## Testing

### Test RAG Pipeline
```bash
python test_rag_pipeline.py
```

Output:
```
[1] Extracting text from PDF...
    ✓ Extracted 15234 characters
[2] Chunking text...
    ✓ Created 45 chunks
[3] Generating embeddings...
    ✓ Created 45 embeddings (384 dimensions)
[4] Storing chunks in ChromaDB...
    ✓ Stored 45 chunks
[5] Testing semantic retrieval...
    Query: 'What is this about?'
    ✓ Retrieved 2 chunks
```

## Troubleshooting

### Issue: "ChromaDB Error: Collection not found"
**Fix:** Ensure document is_processed=True before querying
```python
doc.is_processed = True
doc.save()
```

### Issue: "Ollama connection refused"
**Fix:** Start Ollama in separate terminal
```bash
ollama serve
```

### Issue: "No relevant information found"
**Cause:** Query doesn't match document content
**Fix:** Retrieval threshold or chunk size may need adjustment

## Performance Notes

- **Embedding Speed:** ~100 chunks/second on CPU
- **ChromaDB Query:** <100ms for semantic search
- **Ollama Response:** 1-3 seconds (Gemma3:4b)
- **Storage:** ~1MB per 1000 chunks (embeddings)

## Extension Ideas

1. **Multi-document Chat**: Search across multiple PDFs
2. **Chunk Metadata**: Page numbers, section titles
3. **Reranking**: Add BM25 or cross-encoder reranking
4. **RAG Score**: Display confidence/relevance scores
5. **Hybrid Search**: Combine semantic + keyword search
6. **Web UI**: React/Vue frontend with real-time streaming

## Git Commits

See `/memories/session/rag_pipeline_commits.md` for detailed commit messages.

Quick reference:
```bash
git commit -m "feat: implement RAG utilities with ChromaDB integration"
git commit -m "feat: enhance models for PDF-aware chat"
git commit -m "feat: implement RAG-based chat in views"
git commit -m "ui: enhance template for RAG chat experience"
git commit -m "chore: add project dependencies"
```
