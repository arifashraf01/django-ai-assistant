# RAG Pipeline - Quick Reference Card

## System Overview

```
PDF Upload → Extract → Chunk → Embed → Store in ChromaDB
                                           ↓
User Query → Embed → Search → Retrieve 3-5 chunks → Build RAG Prompt → Ollama → Answer
```

## 1️⃣ Installation (First Time)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run migrations
python manage.py makemigrations
python manage.py migrate

# 3. Start Ollama (new terminal)
ollama serve

# 4. Pull model (if needed)
ollama pull gemma3:4b

# 5. Start Django (new terminal)
python manage.py runserver

# 6. Access http://localhost:8000
```

## 2️⃣ File Structure

| File | Purpose | Size |
|------|---------|------|
| `chat/rag_utils.py` | RAG pipeline core | 150 lines |
| `chat/views.py` | Chat logic | 85 lines |
| `chat/models.py` | Data models | 35 lines |
| `chat/pdf_utils.py` | PDF extraction | 25 lines |
| `chat/embedding_utils.py` | Embeddings | 10 lines |
| `requirements.txt` | Dependencies | 5 lines |

## 3️⃣ Key Functions

### RAG Pipeline
```python
from chat.rag_utils import (
    store_document_chunks,      # Embed & save chunks
    retrieve_relevant_chunks,   # Semantic search
    build_rag_prompt,           # Build prompt
    get_rag_response            # Get Ollama answer
)

# Usage
chunks = retrieve_relevant_chunks(doc_id=1, query="What is this?")
response = get_rag_response(doc_id=1, user_question="Summarize")
```

### PDF Processing
```python
from chat.pdf_utils import extract_text_from_pdf, chunk_text

text = extract_text_from_pdf("path/to/file.pdf")
chunks = chunk_text(text, chunk_size=500)
```

### Embeddings
```python
from chat.embedding_utils import model

embeddings = model.encode(["text 1", "text 2"])
# Returns: numpy array of 384-dimensional vectors
```

## 4️⃣ Database Models

### Document
```python
class Document:
    file              : FileField    # Uploaded PDF
    uploaded_at       : DateTime     # When uploaded
    is_processed      : Boolean      # ChromaDB ready?
```

### ChatMessage
```python
class ChatMessage:
    user_message      : TextField    # User's question
    ai_response       : TextField    # AI's answer
    document          : FK(Document) # Which PDF?
    created_at        : DateTime     # When asked
```

## 5️⃣ Testing Commands

```bash
# Test PDF extraction
python test_pdf.py

# Test RAG pipeline
python test_rag_pipeline.py

# Interactive testing
python manage.py shell
>>> from chat.models import Document
>>> doc = Document.objects.first()
>>> from chat.rag_utils import get_rag_response
>>> response = get_rag_response(doc.id, "What is this?")
>>> print(response)
```

## 6️⃣ Common Operations

### Store PDF in ChromaDB
```python
from chat.models import Document
from chat.pdf_utils import extract_text_from_pdf, chunk_text
from chat.rag_utils import store_document_chunks

doc = Document.objects.last()
text = extract_text_from_pdf(doc.file.path)
chunks = chunk_text(text)
chunks_stored = store_document_chunks(doc.id, chunks)
doc.is_processed = True
doc.save()
```

### Get Answer
```python
from chat.rag_utils import get_rag_response

response = get_rag_response(
    doc_id=1,
    user_question="What is this document about?"
)
print(response)
```

### Inspect Retrieval
```python
from chat.rag_utils import retrieve_relevant_chunks

chunks = retrieve_relevant_chunks(
    doc_id=1,
    query="Key topics",
    top_k=3
)
for i, chunk in enumerate(chunks):
    print(f"\n[Chunk {i}]\n{chunk}")
```

## 7️⃣ Troubleshooting

| Issue | Fix |
|-------|-----|
| `chromadb` not found | `pip install chromadb==0.4.21` |
| Ollama connection error | `ollama serve` in separate terminal |
| No relevant info found | Try simpler keywords or different PDF |
| DB migration error | `rm db.sqlite3 && python manage.py migrate` |
| PDF extraction empty | Check if PDF has text (not image scan) |

## 8️⃣ Performance Tuning

### Faster Responses
```python
# In chat/views.py, line 40:
chunks = chunk_text(text, chunk_size=1000)  # Larger chunks
```

### Better Context
```python
# In chat/rag_utils.py, line 95:
chunks = retrieve_relevant_chunks(doc_id, query, top_k=5)  # More chunks
```

### Lighter Model (Slower but Cheaper)
```python
# In chat/embedding_utils.py:
model = SentenceTransformer("distiluse-base-multilingual-cased-v2")
```

## 9️⃣ Git Commits

```bash
# 1. RAG utils
git add chat/rag_utils.py requirements.txt
git commit -m "feat: implement RAG utilities with ChromaDB"

# 2. Models
git add chat/models.py
git commit -m "feat: enhance models for PDF-aware chat"

# 3. Views
git add chat/views.py
git commit -m "feat: implement RAG-based chat in views"

# 4. UI
git add chat/templates/chat/chat.html
git commit -m "ui: enhance template for RAG chat"

# 5. Docs
git add *.md requirements.txt
git commit -m "chore: add documentation and dependencies"
```

## 🔟 Architecture at a Glance

```
┌─────────────────┐
│  User Uploads   │
│     PDF         │
└────────┬────────┘
         ↓
┌────────────────────────────────────────┐
│ Extract Text                           │
│ ↓ Chunk (500 chars)                    │
│ ↓ Generate Embeddings (384-dim)        │
│ ↓ Store in ChromaDB                    │
└────────┬────────────────────────────────┘
         ↓
┌────────────────────────────────────────┐
│ Document Stored & Ready                │
│ - doc.is_processed = True              │
│ - Embeddings in ChromaDB               │
│ - User can now query                   │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────────────────────────────┐
│ User Asks Question                      │
└────────┬──────────────────────────────────┘
         ↓
┌────────────────────────────────────────┐
│ 1. Embed query (384-dim)               │
│ 2. Search ChromaDB (cosine sim)        │
│ 3. Get top 3-5 chunks                  │
│ 4. Build RAG Prompt                    │
│ 5. Send to Ollama                      │
│ 6. Return grounded answer              │
└────────┬────────────────────────────────┘
         ↓
┌─────────────────┐
│  User Gets      │
│  RAG Response   │
└─────────────────┘
```

## 📊 Data Flow Example

**Upload "research.pdf"**
```
Text (15,000 chars)
  ↓
Chunks (30)
  ↓
Embeddings (30 × 384-dim)
  ↓
ChromaDB col "doc_5"
```

**Ask "What's the main idea?"**
```
Query "What's the main idea?"
  ↓
Embedding (384-dim)
  ↓
ChromaDB search
  ↓
Chunks [chunk_5, chunk_12, chunk_8]
  ↓
RAG Prompt
  ↓
Ollama Gemma3:4b
  ↓
"The main idea is..."
```

## ✅ Verification Checklist

```bash
□ Dependencies installed: pip list | grep chromadb
□ Ollama running: ollama list | grep gemma3
□ Django migrations: python manage.py migrate
□ Models updated: python -c "from chat.models import Document; print(Document._meta.fields)"
□ rag_utils.py exists: test -f chat/rag_utils.py
□ Pipeline works: python test_rag_pipeline.py
□ Web UI running: python manage.py runserver
```

## 🎯 Success Indicators

✅ Can upload PDF without error  
✅ Document marked as `is_processed = True`  
✅ ChromaDB stores embeddings (~1MB per 1000 chunks)  
✅ Query returns results in <5 seconds  
✅ Answers match PDF content (not generic)  
✅ Chat history shows document context  

## 📚 Documentation Files

| File | Contains |
|------|----------|
| INDEX.md | Navigation guide (START) |
| IMPLEMENTATION_SUMMARY.md | Overview & commits |
| SETUP.md | Installation & config |
| CHECKLIST.md | Quick reference |
| RAG_IMPLEMENTATION.md | Architecture details |
| README.md (this) | Quick reference card |

---

**Pro Tip**: Print this card and keep it handy while setting up!

**Version**: 1.0 | **Updated**: 2024 | **Status**: Production Ready
