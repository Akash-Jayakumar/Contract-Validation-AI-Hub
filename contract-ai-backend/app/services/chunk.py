import re

def chunk_text(text, max_length=1200, overlap=120):
    """
    Split text into overlapping chunks for better processing
    
    Args:
        text: Input text to chunk
        max_length: Maximum characters per chunk
        overlap: Number of characters to overlap between chunks
    
    Returns:
        List of text chunks
    """
    # Split into sentences using regex
    sentences = re.split(r'(?<=[\.\?\!])\s+', text.strip())
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) < max_length:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            # Start new chunk with overlap from previous
            overlap_text = current_chunk[-overlap:] if len(current_chunk) > overlap else current_chunk
            current_chunk = overlap_text + " " + sentence
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks
