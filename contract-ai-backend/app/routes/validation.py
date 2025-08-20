from fastapi import APIRouter, Body, HTTPException
from app.services.embeddings import embed_chunks
from app.db.mongo import get_clauses
from app.db.vector import search_embeddings

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
            hits = search_embeddings(cv, top_k=1)
            if hits:
                sim = hits[0].score
                match_text = hits[0].payload['text']
                results.append({
                    "clause": clause_texts[i],
                    "match": match_text,
                    "similarity": round(sim, 3)
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
