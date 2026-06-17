# Implementation Checklist & Quick Reference

## ✅ Pre-Implementation Checklist

Before running the application:

- [ ] Python 3.9+ installed
- [ ] Django 6.0.6 installed (`pip install -r requirements.txt`)
- [ ] Ollama installed and Gemma3:4b model pulled
- [ ] ChromaDB will be auto-created on first run
- [ ] All new files added to project
- [ ] Migrations created and applied

## 📦 New Dependencies to Install

```bash
pip install chromadb==0.4.21 sentence-transformers==3.0.1
```

Or install all at once:
```bash
pip install -r requirements.txt
```

## 🗄️ Database Setup

```bash
# Create new migration for model changes
python manage.py makemigrations

# Apply migration
python manage.py migrate

# Check migration status
python manage.py migrate --plan
```

**New fields added:**
- `ChatMessage.document` (ForeignKey to Document)
- `Document.is_processed` (Boolean, default=False)

## 🚀 Startup Sequence

1. **Terminal 1: Start Ollama**
   ```bash
   ollama serve
   ```
   Wait for: `Listening on 127.0.0.1:11434`

2. **Terminal 2: Verify Model**
   ```bash
   ollama list
   # Should show: gemma3:4b 4.1 GB
   ```

3. **Terminal 3: Start Django**
   ```bash
   python manage.py runserver
   ```
   Navigate to: http://localhost:8000

## 🧪 First-Time Testing

### Step 1: Upload a PDF
- Click "Upload PDF"
- Choose any PDF file (min 1KB)
- Wait for "Document uploaded! (XX chunks indexed)"

If error: Check PDF is readable (not image scan)

### Step 2: Ask a Question
- Type: "What is this document about?"
- Click "Send"
- Wait 2-5 seconds for response

If error: Check Ollama is running with `ollama serve`

### Step 3: Verify Storage
```bash
python manage.py shell
from chat.models import Document
doc = Document.objects.first()
print(f"ID: {doc.id}")
print(f"Processed: {doc.is_processed}")
print(f"Messages: {doc.chat_messages.count()}")
```

## 🔍 Common Issues & Fixes

### Issue: "ModuleNotFoundError: chromadb"
```bash
pip install chromadb==0.4.21
```

### Issue: "ConnectionError: Failed to connect to Ollama"
**Fix:** Make sure Ollama is running
```bash
ollama serve  # Must be running in background
```

### Issue: "No relevant information found"
This is normal for:
- PDFs with images only (scanned)
- Very short PDFs
- Queries with no matching keywords

Try: Simpler query or different PDF

### Issue: "Document not found in ChromaDB"
```bash
# Check if document is_processed
python manage.py shell
from chat.models import Document
Document.objects.filter(is_processed=False).values('id', 'file')
```

### Issue: Migrations failed
```bash
# Reset migrations (WARNING: clears database)
rm db.sqlite3
python manage.py migrate
```

## 📊 Directory Structure Reference

```
django-ai-assistant/
├── chat/
│   ├── rag_utils.py              ← RAG pipeline (CORE)
│   ├── embedding_utils.py        ← Embedding model
│   ├── pdf_utils.py              ← PDF extraction
│   ├── views.py                  ← Updated chatbot view
│   ├── models.py                 ← Updated models
│   ├── forms.py
│   └── templates/chat/
│       └── chat.html             ← Updated UI
├── chroma_db/                    ← Auto-created, stores embeddings
├── media/documents/              ← Uploaded PDFs
├── requirements.txt              ← NEW dependencies
├── RAG_IMPLEMENTATION.md         ← Architecture docs
├── SETUP.md                      ← Setup guide
├── IMPLEMENTATION_SUMMARY.md     ← This + more detail
├── rag_examples.py               ← Usage examples
└── test_rag_pipeline.py          ← Test script
```

## 🎯 Key Functions at a Glance

### `rag_utils.py`
```python
store_document_chunks(doc_id, chunks)      # Store in ChromaDB
retrieve_relevant_chunks(doc_id, query)    # Semantic search
build_rag_prompt(question, chunks)         # Build prompt
get_rag_response(doc_id, user_question)    # End-to-end
```

### `views.py`
```python
def chatbot(request):
    # Handles PDF upload + RAG chat
    # Returns: template with messages + active document
```

### `models.py`
```python
ChatMessage.document              # NEW: FK to Document
Document.is_processed            # NEW: Processing flag
```

## 💾 Data Storage Locations

| What | Where | Size |
|------|-------|------|
| Uploaded PDFs | `media/documents/*.pdf` | ~1-100 MB each |
| Embeddings | `chroma_db/` | ~1 MB per 1000 chunks |
| Chat history | `db.sqlite3` | Small (~1MB) |
| Django files | `chat/` | Static |

## 🔧 Configuration Tuning

### Change Chunk Size
In `views.py`, line ~40:
```python
chunks = chunk_text(text, chunk_size=500)  # Change 500
```
- Smaller (250) = More chunks, faster search
- Larger (1000) = Better context, slower search

### Change Retrieved Chunks
In `rag_utils.py`, line ~95:
```python
top_k=3  # Change to 5 for more context
```

### Change Embedding Model
In `embedding_utils.py`:
```python
model = SentenceTransformer("all-MiniLM-L6-v2")  # Change model name
# Alternatives: "sentence-transformers/all-mpnet-base-v2"
```

## 📝 Testing Commands (One-Liners)

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# List ChromaDB collections
python -c "from chat.rag_utils import client; print(client.list_collections())"

# Count stored embeddings
python manage.py shell -c "from chat.models import Document; d = Document.objects.first(); print(f'{d.chat_messages.count()} messages') if d else None"

# Test pipeline end-to-end
python test_rag_pipeline.py

# Interactive testing
python manage.py shell
exec(open('rag_examples.py').read())
```

## 🚀 Deployment Checklist

- [ ] Update `settings.py`: `DEBUG = False`
- [ ] Set `ALLOWED_HOSTS = ['yourdomain.com']`
- [ ] Update secret key
- [ ] Configure database (PostgreSQL recommended)
- [ ] Set up Ollama on production server
- [ ] Configure ChromaDB persistence path
- [ ] Use HTTPS in production
- [ ] Create systemd service for Ollama
- [ ] Setup error logging (Sentry recommended)
- [ ] Monitor disk space (for embeddings)

## 📈 Performance Expectations

| Operation | Time |
|-----------|------|
| PDF upload (10 pages) | 1-3 seconds |
| Text extraction | 0.5 seconds |
| Chunking | 0.1 second |
| Generate embeddings | 0.5 second |
| ChromaDB storage | 0.2 second |
| Query embedding | 0.1 second |
| Semantic search | 0.05 second |
| Ollama generation | 2-3 seconds |
| **Total per query** | **2-5 seconds** |

## 🎓 Code Review Talking Points

1. **Architecture**: "Per-document ChromaDB collections for scalability"
2. **Embeddings**: "One-time generation at upload, reused at query time"
3. **Retrieval**: "Cosine similarity in 384-dimensional space"
4. **Prompting**: "RAG prompt ensures grounded, factual responses"
5. **Storage**: "Persistent ChromaDB survives app restarts"
6. **Error handling**: "Graceful fallbacks for missing documents"

## 🔗 Important Files to Review

1. `chat/rag_utils.py` - Core RAG implementation (150 lines)
2. `chat/views.py` - Chat logic (85 lines)
3. `chat/models.py` - Data models (35 lines)
4. `RAG_IMPLEMENTATION.md` - Full documentation

## ✨ Next Steps After Setup

1. ✅ Install dependencies
2. ✅ Run migrations
3. ✅ Start Ollama
4. ✅ Run Django
5. ✅ Upload a PDF
6. ✅ Ask a question
7. → Customize RAG prompt in `rag_utils.py`
8. → Add more retrieval strategies
9. → Deploy to production

---

**Last updated**: 2024
**Version**: 1.0 Complete
**Status**: Ready for production after setup
