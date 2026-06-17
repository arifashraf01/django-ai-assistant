# RAG Pipeline Setup Guide

## Prerequisites

- Python 3.9+
- Ollama installed and running
- 500MB+ disk space for ChromaDB and embeddings

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

**What's installed:**
- `Django 6.0.6` - Web framework
- `pypdf 4.0.1` - PDF text extraction
- `sentence-transformers 3.0.1` - Embedding model (22MB download)
- `chromadb 0.4.21` - Vector database
- `ollama 0.1.34` - Ollama client

### 2. Run Database Migrations

Create new migrations for the model changes:

```bash
python manage.py makemigrations
python manage.py migrate
```

**What changes:**
- `ChatMessage` now has `document` ForeignKey
- `Document` now has `is_processed` boolean field

### 3. Start Ollama

In a separate terminal:

```bash
ollama serve
```

In another terminal, pull the model:

```bash
ollama pull gemma3:4b
```

**Verify it works:**
```bash
ollama list
# Should show: gemma3:4b    4.1 GB
```

### 4. Run Django Development Server

```bash
python manage.py runserver
```

Access at: `http://localhost:8000`

### 5. Test the System

#### Test 1: Upload a PDF

1. Open http://localhost:8000
2. Choose a PDF file
3. Click "Upload PDF"
4. Wait for processing (1-3 seconds)
5. You should see "Document uploaded! (XX chunks indexed)"

#### Test 2: Ask a Question

1. Type a question: "What is this document about?"
2. Click "Send"
3. Wait for response (2-5 seconds)
4. Response should be based on PDF content

#### Test 3: Verify ChromaDB Storage

```bash
python manage.py shell
```

```python
from chat.models import Document
from chat.rag_utils import retrieve_relevant_chunks

doc = Document.objects.first()
chunks = retrieve_relevant_chunks(doc.id, "test query", top_k=2)
print(f"Retrieved {len(chunks)} chunks")
print(chunks[0][:100])
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'chromadb'"

```bash
pip install chromadb==0.4.21
```

### Issue: "ConnectionError: Failed to connect to Ollama"

**Solution:** Make sure Ollama is running in another terminal:
```bash
ollama serve
```

### Issue: "No relevant information found in the uploaded document"

This means the query didn't match any chunks. Try:
1. Check if PDF has readable content (not scanned image)
2. Use simpler keywords
3. Increase chunk size in `chat/pdf_utils.py`:
   ```python
   chunks = chunk_text(text, chunk_size=1000)  # Larger chunks
   ```

### Issue: Django migration error

Clear old migration files and restart:
```bash
rm db.sqlite3
rm -rf chat/migrations/__pycache__
python manage.py makemigrations
python manage.py migrate
```

### Issue: "PDF extraction returns empty text"

The PDF might be scanned images. Check:
```bash
python test_pdf.py
# Output should show chunks and embeddings
```

## File Structure

```
django-ai-assistant/
├── chat/
│   ├── embedding_utils.py      # Embedding model
│   ├── pdf_utils.py             # PDF extraction & chunking
│   ├── rag_utils.py             # RAG pipeline ⭐ NEW
│   ├── models.py                # Updated models
│   ├── views.py                 # Updated views
│   ├── templates/chat/
│   │   └── chat.html            # Updated UI
│   └── migrations/
│       └── 0003_*.py            # New migration ⭐
├── config/
│   └── settings.py
├── chroma_db/                   # ChromaDB storage ⭐ NEW
│   ├── *.bin                    # Embeddings
│   ├── index.bin
│   └── ...
├── requirements.txt             # Dependencies ⭐ NEW
├── RAG_IMPLEMENTATION.md        # Architecture docs ⭐ NEW
├── rag_examples.py              # Usage examples ⭐ NEW
├── test_rag_pipeline.py         # RAG pipeline test ⭐ NEW
└── manage.py
```

## Quick Test Commands

### 1. Test PDF Extraction
```bash
python test_pdf.py
```

### 2. Test RAG Pipeline
```bash
python test_rag_pipeline.py
```

### 3. Interactive Testing in Django Shell
```bash
python manage.py shell
exec(open('rag_examples.py').read())
ask_about_document(1, "What is this about?")
```

### 4. Check Stored Documents
```bash
python manage.py shell
from chat.models import Document
Document.objects.all().values('id', 'file', 'is_processed')
```

## Performance Tuning

### Faster Embedding (Lower Quality)
Replace `all-MiniLM-L6-v2` with smaller model in `embedding_utils.py`:
```python
model = SentenceTransformer("all-MiniLM-L6-v2")  # 22MB, 384-dim (current)
# model = SentenceTransformer("all-MiniLM-L6-v2")  # 1.7MB, 96-dim (faster)
```

### Larger Chunks (Faster Retrieval, Less Context)
In `views.py`, change chunk size:
```python
chunks = chunk_text(text, chunk_size=1000)  # Default 500
```

### More Retrieved Chunks (Better Context)
In `rag_utils.py`, change top_k:
```python
chunks = retrieve_relevant_chunks(doc_id, query, top_k=5)  # Default 3
```

### Disable Ollama Streaming (Faster Response)
The ollama library doesn't support streaming by default. For streaming:
```bash
curl http://localhost:11434/api/chat -d '{"model": "gemma3:4b", "stream": true}'
```

## Monitoring & Debugging

### Check ChromaDB Collections
```bash
python manage.py shell
from chat.rag_utils import client
collections = client.list_collections()
for col in collections:
    print(f"{col.name}: {col.count()} chunks")
```

### View Stored Embeddings
```bash
python manage.py shell
from chat.rag_utils import get_or_create_collection
col = get_or_create_collection(1)
data = col.get()
print(f"Total chunks: {len(data['ids'])}")
print(f"Metadata: {data['metadatas'][:2]}")
```

### Monitor Chat Messages
```bash
python manage.py shell
from chat.models import ChatMessage
ChatMessage.objects.all().values('id', 'user_message', 'document_id', 'created_at')
```

## Next Steps

1. ✅ Setup complete - run `python manage.py runserver`
2. 📄 Upload a PDF
3. ❓ Ask questions about it
4. 🚀 Deploy to production (update DEBUG=False in settings.py)

## Need Help?

Refer to:
- [RAG_IMPLEMENTATION.md](RAG_IMPLEMENTATION.md) - Architecture & design
- [rag_examples.py](rag_examples.py) - Code examples
- [test_rag_pipeline.py](test_rag_pipeline.py) - Testing workflow
