import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import uuid

class ChromaDBManager:
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB client and collection management"""
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        self.collections = {}
        
    def get_or_create_collection(self, name: str) -> Any:
        """Get or create a collection"""
        if name not in self.collections:
            self.collections[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"}
            )
        return self.collections[name]
    
    def add_documents(self, 
                     documents: List[str], 
                     embeddings: List[List[float]], 
                     metadatas: List[Dict[str, Any]], 
                     ids: List[str],
                     collection_name: str = "contracts") -> None:
        """Add documents with embeddings to ChromaDB"""
        collection = self.get_or_create_collection(collection_name)
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )
    
    def search_similar(self, 
                      query_embedding: List[float], 
                      collection_name: str = "contracts",
                      top_k: int = 5,
                      where: Optional[Dict] = None) -> Dict[str, Any]:
        """Search for similar documents"""
        collection = self.get_or_create_collection(collection_name)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where
        )
        return results
    
    def get_collection_count(self, collection_name: str = "contracts") -> int:
        """Get count of documents in collection"""
        collection = self.get_or_create_collection(collection_name)
        return collection.count()
    
    def delete_collection(self, collection_name: str) -> None:
        """Delete a collection"""
        if collection_name in self.collections:
            del self.collections[collection_name]
        try:
            self.client.delete_collection(collection_name)
        except:
            pass
    
    def get_collection_info(self, collection_name: str = "contracts") -> Dict[str, Any]:
        """Get collection information"""
        collection = self.get_or_create_collection(collection_name)
        return {
            "name": collection_name,
            "count": collection.count(),
            "metadata": collection.metadata
        }

# Global instance
chroma_manager = ChromaDBManager()

# Convenience functions for backward compatibility
def search_embeddings(query_embedding: List[float], collection_name: str = "contracts", top_k: int = 5) -> Dict[str, Any]:
    """Search for similar documents using embeddings"""
    return chroma_manager.search_similar(
        query_embedding=query_embedding,
        collection_name=collection_name,
        top_k=top_k
    )

def get_collection_info(collection_name: str = "contracts") -> Dict[str, Any]:
    """Get collection information"""
    return chroma_manager.get_collection_info(collection_name)

def store_embedding(text: str, embedding: List[float], metadata: Dict[str, Any], doc_id: str, collection_name: str = "contracts") -> None:
    """Store a single embedding"""
    chroma_manager.add_documents(
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata],
        ids=[doc_id],
        collection_name=collection_name
    )
