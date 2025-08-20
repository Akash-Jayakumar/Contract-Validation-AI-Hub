from qdrant_client import QdrantClient
from qdrant_client.http.models import VectorParams, PointStruct, Distance
from app.config import QDRANT_URL

client = QdrantClient(QDRANT_URL)
DIM = 384  # Dimension for all-MiniLM-L6-v2

def ensure_collection(name="contracts_default"):
    """Ensure collection exists, create if it doesn't"""
    colls = [c.name for c in client.get_collections().collections]
    if name not in colls:
        client.recreate_collection(
            name,
            vectors_config=VectorParams(size=DIM, distance=Distance.COSINE)
        )

def add_embeddings(vectors, payloads, name="contracts_default"):
    """Add embeddings to vector database"""
    ensure_collection(name)
    points = [PointStruct(id=i, vector=v, payload=payloads[i]) for i, v in enumerate(vectors)]
    client.upsert(name, points=points)

def search_embeddings(query_vector, top_k=5, name="contracts_default"):
    """Search for similar embeddings"""
    ensure_collection(name)
    return client.search(name, query_vector=query_vector, limit=top_k)

def delete_collection(name="contracts_default"):
    """Delete a collection"""
    client.delete_collection(name)

def get_collection_info(name="contracts_default"):
    """Get collection information"""
    return client.get_collection(name)
