from fastapi import APIRouter, Body, HTTPException
from app.services.embeddings import embed_text, semantic_search

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
        results = semantic_search(question, top_k=5)
        
        # Prepare context from search results
        if results and results.get('documents'):
            context = "\n".join([doc for doc in results['documents'][0]])
        else:
            context = ""
        
        return {
            "question": question,
            "context": context,
            "matches": len(results.get('documents', [[]])[0]) if results else 0
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
