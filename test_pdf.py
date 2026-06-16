from chat.pdf_utils import (
    extract_text_from_pdf,
    chunk_text
)

pdf_path = "media/documents/arif_resume.pdf"

text = extract_text_from_pdf(pdf_path)

chunks = chunk_text(text)

print(f"Total chunks: {len(chunks)}")

print("\nFIRST CHUNK:\n")
print(chunks[0])