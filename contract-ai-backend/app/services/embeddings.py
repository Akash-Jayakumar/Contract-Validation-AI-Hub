from sentence_transformers import SentenceTransformer
import numpy as np
from app.db.vector import chroma_manager
from typing import List, Dict, Any
import uuid

# Initialize the model
model = SentenceTransformer("all-MiniLM-L6-v2")

def embed_chunks(chunks: List[str]) -> List[List[float]]:
    """
    Generate embeddings for text chunks
    
    Args:
        chunks: List of text chunks
    
    Returns:
        List of embedding vectors
    """
    return model.encode(chunks, normalize_embeddings=True)

def embed_text(text: str) -> List[float]:
    """
    Generate embedding for single text
    
    Args:
        text: Input text
    
    Returns:
        Embedding vector
    """
    return model.encode([text], normalize_embeddings=True)[0]

def store_embeddings(
    contract_id: str,
    chunks: List[str],
    embeddings: List[List[float]],
    titles: None = None,  # legacy param not used when metadatas provided
    metadatas: None = None
) -> List[str]:
    """
    Store chunks and embeddings in ChromaDB
    
    Args:
        contract_id: Unique contract identifier
        chunks: List of text chunks
        embeddings: List of embedding vectors
        titles: Optional list of titles (legacy)
        metadatas: Optional list of metadata dicts
    
    Returns:
        List of document IDs
    """
    if metadatas is None:
        metadatas = []
        for i in range(len(chunks)):
            md = {"contract_id": contract_id, "chunk_index": i}
            if titles and i < len(titles):
                md["title"] = titles[i]
            metadatas.append(md)
    ids = [str(uuid.uuid4()) for _ in chunks]
    
    chroma_manager.add_documents(
        documents=chunks,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids,
        collection_name="contracts"
    )
    return ids

def semantic_search(query: str, top_k: int = 5, contract_id: str = None) -> Dict[str, Any]:
    """
    Perform semantic search across contracts
    
    Args:
        query: Search query
        top_k: Number of results to return
        contract_id: Optional filter by contract ID
    
    Returns:
        Search results from ChromaDB
    """
    query_embedding = embed_text(query)
    
    where_filter = None
    if contract_id:
        where_filter = {"contract_id": contract_id}
    
    return chroma_manager.search_similar(
        query_embedding=query_embedding,
        top_k=top_k,
        where=where_filter,
        collection_name="contracts"
    )

def get_contract_chunks(contract_id: str) -> Dict[str, Any]:
    """
    Get all chunks for a specific contract
    
    Args:
        contract_id: Contract identifier
    
    Returns:
        All chunks for the contract
    """
    return chroma_manager.search_similar(
        query_embedding=[0.0] * 384,  # Dummy embedding
        where={"contract_id": contract_id},
        top_k=1000,
        collection_name="contracts"
    )

def delete_contract_embeddings(contract_id: str) -> None:
    """
    Delete all embeddings for a specific contract
    
    Args:
        contract_id: Contract identifier
    """
    # This would require implementing delete_by_metadata in ChromaDBManager
    pass
