from sentence_transformers import SentenceTransformer
import numpy as np

# Initialize the model
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_chunks(chunks):
    """
    Generate embeddings for text chunks
    
    Args:
        chunks: List of text chunks
    
    Returns:
        List of embedding vectors
    """
    return model.encode(chunks, normalize_embeddings=True)

def embed_text(text):
    """
    Generate embedding for single text
    
    Args:
        text: Input text
    
    Returns:
        Embedding vector
    """
    return model.encode([text], normalize_embeddings=True)[0]
