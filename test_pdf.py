from chat.pdf_utils import (
    extract_text_from_pdf,
    chunk_text
)

from chat.embedding_utils import (
    create_embeddings
)

pdf_path = "media/documents/arif_resume.pdf"

text = extract_text_from_pdf(pdf_path)

chunks = chunk_text(text)

embeddings = create_embeddings(chunks)

print("Chunks:", len(chunks))
print("Embeddings:", len(embeddings))
print("Vector Length:", len(embeddings[0]))