from pypdf import PdfReader


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract all text from a PDF file at *pdf_path*.

    Returns the concatenated text of all pages. Empty pages are skipped.
    Raises ``ValueError`` if no text could be extracted.
    """
    reader = PdfReader(pdf_path)
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text)
    return "\n".join(parts)


def chunk_text(text: str, chunk_size: int = 500) -> list[str]:
    """Split *text* into non-overlapping chunks of at most *chunk_size* chars.

    Chunks are broken on whitespace boundaries so words are not split mid-token.
    Empty or whitespace-only chunks are discarded.
    """
    if not text:
        return []

    words = text.split()
    chunks: list[str] = []
    current_parts: list[str] = []
    current_len = 0

    for word in words:
        # +1 for the space separator (except the first word in a chunk)
        word_len = len(word) + (1 if current_parts else 0)
        if current_parts and current_len + word_len > chunk_size:
            chunks.append(" ".join(current_parts))
            current_parts = [word]
            current_len = len(word)
        else:
            current_parts.append(word)
            current_len += word_len

    if current_parts:
        chunks.append(" ".join(current_parts))

    return chunks