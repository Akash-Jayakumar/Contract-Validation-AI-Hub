from fastapi import APIRouter, HTTPException
from app.services.embeddings import get_contract_chunks   # reuse Chroma access
from app.utils.clause_analysis import analyze_contract

router = APIRouter()

@router.get("/{contract_id}")
async def get_contract_checklist(contract_id: str):
    """Return checklist analysis for a contract using ChromaDB chunks"""
    try:
        results = get_contract_chunks(contract_id)

        if not results['documents'] or not results['documents'][0]:
            raise HTTPException(status_code=404, detail="No chunks found for this contract")

        # Join all chunks back into one text
        text_content = " ".join(results['documents'][0])

        # Run AI / rules-based analysis
        checklist = analyze_contract(text_content)

        return {
            "contract_id": contract_id,
            "checklist": checklist,
            "chunks_analyzed": len(results['documents'][0])
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Checklist error: {e}")
