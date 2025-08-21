from fastapi import APIRouter, Body, HTTPException
from app.services.embeddings import embed_chunks
from app.db.mongo import get_clauses
from app.db.vector import chroma_manager

router = APIRouter()

@router.post("/{contract_id}/validate")
def validate_contract(contract_id: str, body: dict = Body(...)):
    """Validate contract against clause library"""
    try:
        clauses = get_clauses()
        if not clauses:
            raise HTTPException(status_code=404, detail="No clauses found in library")
        
        clause_texts = [c["text"] for c in clauses]
        clause_vecs = embed_chunks(clause_texts)
        
        # For each clause, search vectorDB for best match
        results = []
        for i, cv in enumerate(clause_vecs):
            search_results = chroma_manager.search_similar(
                query_embedding=cv,
                top_k=1,
                collection_name="contracts"
            )
            
            if search_results and search_results.get('documents') and search_results['documents'][0]:
                # Get the first match
                match_text = search_results['documents'][0][0]
                # Calculate similarity (ChromaDB returns distances, convert to similarity)
                if search_results.get('distances') and search_results['distances'][0]:
                    distance = search_results['distances'][0][0]
                    similarity = 1 - distance  # Convert distance to similarity
                else:
                    similarity = 0.0
                
                results.append({
                    "clause": clause_texts[i],
                    "match": match_text,
                    "similarity": round(similarity, 3)
                })
            else:
                results.append({
                    "clause": clause_texts[i],
                    "match": "",
                    "similarity": 0.0
                })
        
        return {"contract_id": contract_id, "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")
