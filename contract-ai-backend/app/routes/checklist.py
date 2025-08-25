from fastapi import APIRouter, HTTPException
from app.services.embeddings import semantic_search
from app.services.llm import gemini_json

router = APIRouter(prefix="/checklist", tags=["checklist"])

# Fixed retrieval size
RETRIEVAL_K = 12  # internal, no query param exposed

DEFAULT_ITEMS = [
    {"key": "confidentiality_clause", "label": "Confidentiality / NDA", "weight": 0.15},
    {"key": "liability_clause", "label": "Limitation of Liability & Indemnity", "weight": 0.25},
    {"key": "payment_terms", "label": "Payment Terms & Late Fees", "weight": 0.15},
    {"key": "intellectual_property", "label": "Intellectual Property Ownership/License", "weight": 0.25},
    {"key": "termination_clause", "label": "Termination & Termination for Convenience", "weight": 0.20},
]

LLM_INSTRUCTIONS = """
You are a contracts analyst. Produce a checklist with justification and risk.
For each item key, output:
- present: true/false
- explanation: short rationale pointing to language and implications
- evidence: a short quote (<=300 chars) or "" if not found
- item_risk: integer 0–5 residual risk (higher = riskier)
Also return overall_risk 0–100 and overall_explanation.
Return only strict JSON:
{
  "items": { "<key>": { "present": bool, "explanation": str, "evidence": str, "item_risk": int }, ... },
  "overall_risk": int,
  "overall_explanation": str
}
"""

def _flatten_to_strings(nested):
    """Flatten nested lists into a single list of strings"""
    flat = []
    for item in nested:
        if isinstance(item, str):
            flat.append(item)
        elif isinstance(item, (list, tuple)):
            flat.extend([s for s in item if isinstance(s, str)])
    return flat

def _build_prompt(chunks, items):
    checklist = "\n".join([f"- {i['key']}: {i['label']}" for i in items])
    # Flatten chunks to handle nested lists from semantic_search
    flat_chunks = _flatten_to_strings(chunks if isinstance(chunks, list) else [])
    context = "\n\n---\n".join(flat_chunks)
    return f"{LLM_INSTRUCTIONS}\n\nChecklist:\n{checklist}\n\nContract excerpts:\n{context}"

@router.get("/{contract_id}")
def checklist(contract_id: str):
    try:
        # Retrieve representative chunks internally (fixed RETRIEVAL_K)
        results = semantic_search(query="contract key clauses", top_k=RETRIEVAL_K, contract_id=contract_id)
        chunks = results["documents"] if results and results.get("documents") else []
        if not chunks:
            return {
                "contract_id": contract_id,
                "checklist": {},
                "chunks_analyzed": 0,
                "overall_risk": 100,
                "overall_explanation": "No content found for this contract; treat as high risk by default."
            }

        prompt = _build_prompt(chunks, DEFAULT_ITEMS)
        analysis = gemini_json(prompt)

        return {
            "contract_id": contract_id,
            "checklist": analysis.get("items", {}),
            "chunks_analyzed": len(chunks),
            "overall_risk": analysis.get("overall_risk", 50),
            "overall_explanation": analysis.get("overall_explanation", "Computed from checklist items.")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
