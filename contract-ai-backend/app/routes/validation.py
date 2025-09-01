from fastapi import APIRouter, Body, HTTPException
from typing import List, Dict, Any
from app.services.embeddings import semantic_search
from app.db.mongo import get_clauses
from app.db.vector import chroma_manager
from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import List, Optional
import uuid
import os
import boto3
import shutil
from app.services.ocr import extract_text_from_pdf, extract_text_from_image
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search, get_contract_chunks
from app.models.contract import ContractUploadResponse, SearchQuery, SearchResponse
from app.db.vector import chroma_manager
router = APIRouter()

CLAUSE_CHECKS = [
    {"name": "Confidentiality", "query": "confidentiality obligations reasonable care survive years"},
    {"name": "Termination for Convenience", "query": "terminate for convenience days notice payment performed"},
    {"name": "Limitation for Liability", "query": "limitation for liability cap exclude consequential damages"},
    {"name": "IP Ownership", "query": "intellectual property ownership license pre-existing"},
]

COMPLIANCE_POLICIES = [
    {"policy": "Payment Terms", "query": "payment terms net 30 late fees capped", "rule": "Net 30 days with capped late fees."},
    {"policy": "Governing Law", "query": "governing law jurisdiction venue", "rule": "Governing law explicitly specified."},
    {"policy": "Data Protection", "query": "consumer data pii gdpr consent", "rule": "Personal data handled properly."},
    {"policy": "Force Majeure", "query": "force majeure suspension", "rule": "Force majeure clause present."},
    {"policy": "Audit Rights", "query": "audit right inspect records", "rule": "Reasonable audit rights."},
]

VIOLATION_POLICIES = [
    {"policy": "Uncapped Liability", "query": "uncapped liability indemnity", "explain": "Uncapped liability clause found.", "threshold": 70, "tag": "Legal"},
    {"policy": "No Termination for Convenience", "query": "no termination convenience clause", "explain": "Missing termination for convenience.", "threshold": 60, "tag": "Operational"},
    {"policy": "Weak Confidentiality", "query": "confidentiality less than one year", "explain": "Confidentiality period too short.", "threshold": 50, "tag": "Data Privacy"},
]

def _score(text: str, include: List[str], exclude: List[str]) -> int:
    txt = (text or "").lower()
    score = 50
    for inc in include:
        if inc in txt:
            score += 10
    for exc in exclude:
        if exc in txt:
            score -= 10
    return max(0, min(100, score))

def _risk_level(score: int) -> str:
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    return "Low"

@router.post("/validate")
def validate_contract(payload: Dict[str, Any] = Body(...)):
    contract_id = payload.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id is required")

    try:
        clauses = get_clauses()
        if not clauses:
            raise HTTPException(status_code=404, detail="No clauses found in library")

        clause_texts = [c["text"] for c in clauses]
        clause_vecs = embed_chunks(clause_texts)

        clause_results = []
        for i, vec in enumerate(clause_vecs):
            res = chroma_manager.search_similar(
                query_embedding=vec,
                top_k=1,
                collection_name="contracts"
            )
            if res and res.get("documents") and res["documents"][0]:
                match_text = res["documents"][0][0]
                distances = res.get("distances")
                distance = distances[0][0] if distances else 1.0
                similarity = 1 - distance
                similarity = round(similarity, 3)
            else:
                match_text = ""
                similarity = 0.0
            clause_results.append({
                "clause": clause_texts[i],
                "match": match_text,
                "similarity": similarity,
            })

        # Now compute the richer validation outputs similarly as we did before,
        # combining clause_results, compliance, violations, etc.
        # For brevity, you can integrate similar logic from our prior code to enrich the output.

        # Example response skeleton:
        return {
            "contract_id": contract_id,
            "clause_results": clause_results,
            # Include "clauses", "compliance", "violations", "risk_score", "risks_involved" from your other function
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
