from fastapi import APIRouter, Body, HTTPException
from app.services.embeddings import embed_text, semantic_search
from app.services.llm import LLMService

router = APIRouter(prefix="/contracts/chat")

@router.post("/")
def chat_contract(query: dict = Body(...)):
    """Chat/Q&A with contracts using vector search and AI"""
    try:
        # Accept contract_id and question explicitly
        question = query.get("question") or query.get("query")
        contract_id = query.get("contract_id")
        if not question:
            raise HTTPException(status_code=400, detail="Question is required")
        if not contract_id:
            raise HTTPException(status_code=400, detail="contract_id is required")

        # Generate embedding for the question
        query_vector = embed_text(question)

        # Search for relevant chunks, filtered by contract_id
        results = semantic_search(question, top_k=5, contract_id=contract_id)
        if results and results.get("documents"):
            context = "\n".join([doc for doc in results["documents"][0]])
            matches = len(results["documents"])
        else:
            context = ""
            matches = 0

        # Generate AI response using the context (LLM with Gemini/etc.)
        response = LLMService.generate_response(question, context)

        return {
            "question": question,
            "contract_id": contract_id,
            "context": context,
            "response": response,
            "matches": matches
        }
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        raise HTTPException(status_code=500, detail=f"Error: {e}\n{tb}")
