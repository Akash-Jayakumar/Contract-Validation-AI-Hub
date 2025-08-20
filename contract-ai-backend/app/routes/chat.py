from fastapi import APIRouter, Body, HTTPException
from app.services.embeddings import embed_text
from app.db.vector import search_embeddings

router = APIRouter()

@router.post("/")
def chat_contract(query: dict = Body(...)):
    """Chat/Q&A with contracts using vector search"""
    try:
        question = query.get("question")
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        
        # Generate embedding for the question
        query_vector = embed_text(question)
        
        # Search for relevant chunks
        hits = search_embeddings(query_vector, top_k=5)
        
        # Prepare context from search results
        context = "\n".join([hit.payload['text'] for hit in hits])
        
        return {
            "question": question,
            "context": context,
            "matches": len(hits)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
