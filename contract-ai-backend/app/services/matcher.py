from typing import List, Dict, Tuple
import numpy as np

def calculate_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calculate cosine similarity between two vectors"""
    return np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))

def find_best_matches(
    query_vector: np.ndarray,
    candidate_vectors: List[np.ndarray],
    candidate_texts: List[str],
    top_k: int = 5
) -> List[Dict]:
    """
    Find best matching clauses based on vector similarity
    
    Args:
        query_vector: Query embedding vector
        candidate_vectors: List of candidate embedding vectors
        candidate_texts: List of candidate texts
        top_k: Number of top matches to return
    
    Returns:
        List of matches with similarity scores
    """
    similarities = []
    
    for i, (vec, text) in enumerate(zip(candidate_vectors, candidate_texts)):
        similarity = calculate_similarity(query_vector, vec)
        similarities.append({
            "index": i,
            "text": text,
            "similarity": float(similarity)
        })
    
    # Sort by similarity descending
    similarities.sort(key=lambda x: x["similarity"], reverse=True)
    
    return similarities[:top_k]
