from fastapi import APIRouter, Body, HTTPException, UploadFile, File
from typing import List, Dict, Any
import uuid
import os
import shutil

from app.services.ocr import extract_text_from_image
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search
from app.models.contract import ContractUploadResponse
from app.db.vector import ChromaDBManager

from pdfminer.high_level import extract_text

router = APIRouter(prefix="/contracts", tags=["contracts"])

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


# --------------------------- Upload Contract ---------------------------
@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    try:
        contract_id = str(uuid.uuid4())
        file_ext = file.filename.lower().rsplit(".", 1)[-1]
        file_path = os.path.join(UPLOAD_DIR, f"{contract_id}.{file_ext}")

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        if file_ext == "pdf":
            text = extract_text(file_path)
        elif file_ext in ("png", "jpg", "jpeg", "tiff", "bmp"):
            text = extract_text_from_image(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        if not text.strip():
            raise HTTPException(status_code=400, detail="No text extracted from document")

        chunks = chunk_text(text)
        embeddings = embed_chunks(chunks)
        doc_ids = store_embeddings(contract_id, chunks, embeddings)

        return ContractUploadResponse(
            contract_id=contract_id,
            filename=file.filename,
            chunks_processed=len(chunks),
            document_ids=doc_ids,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --------------------------- Policy Checks ---------------------------
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
    {"policy": "Force Majeure", "query": "force majeure suspension", "rule": "Force majeure clause present and effective."},
    {"policy": "Audit Rights", "query": "audit right inspect records", "rule": "Reasonable audit rights."},
]

VIOLATION_POLICIES = [
    {"policy": "Uncapped Liability", "query": "uncapped liability indemnity", "explain": "Uncapped liability clause exists.", "threshold": 70, "tag": "Legal"},
    {"policy": "No Termination for Convenience", "query": "no termination convenience clause", "explain": "Missing termination for convenience.", "threshold": 60, "tag": "Operational"},
    {"policy": "Weak Confidentiality", "query": "confidentiality less than one year", "explain": "Confidentiality period too short.", "threshold": 50, "tag": "Data Privacy"},
]


# --------------------------- Helpers ---------------------------
def _score(text: str, includes: List[str], excludes: List[str]) -> int:
    txt = (text or "").lower()
    score = 50
    for inc in includes:
        if inc in txt:
            score += 10
    for exc in excludes:
        if exc in txt:
            score -= 10
    return max(0, min(100, score))


def _risk_level(score: int) -> str:
    if score >= 70:
        return "High"
    elif score >= 40:
        return "Medium"
    return "Low"


# --------------------------- Validate Contract ---------------------------
@router.post("/validation")
def validate_contract(payload: Dict[str, Any] = Body(...)):
    contract_id = payload.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id is required")

    try:
        clauses = []
        for cl in CLAUSE_CHECKS:
            res = semantic_search(query=cl["query"], top_k=3, contract_id=contract_id)
            docs = res.get("documents", [[]])
            snippet = docs[0][0] if docs and docs[0] else ""
            present = bool(snippet)
            strength = 50

            if cl["name"] == "Limitation for Liability":
                strength = _score(snippet, ["cap", "exclude consequential"], ["uncapped", "no cap"])
            elif cl["name"] == "Confidentiality":
                strength = _score(snippet, ["reasonable care", "survive 3 years"], ["less than one year", "weak"])
            elif cl["name"] == "Termination for Convenience":
                strength = _score(snippet, ["mutual", "30 days", "payment"], ["only cause", "90 days"])

            clauses.append({
                "name": cl["name"],
                "present": present,
                "strength": strength,
                "evidence": snippet
            })

        compliance = []
        for cp in COMPLIANCE_POLICIES:
            res = semantic_search(query=cp["query"], top_k=2, contract_id=contract_id)
            docs = res.get("documents", [[]])
            snippet = docs[0][0] if docs and docs[0] else ""
            txt = snippet.lower()
            score = 50

            if cp["policy"] == "Payment Terms":
                if "net 30" in txt or "30 days" in txt:
                    score += 25
                if "late fee" in txt and ("cap" in txt or "not exceed" in txt):
                    score += 10
            elif cp["policy"] == "Governing Law":
                if "governing law" in txt:
                    score += 20
            elif cp["policy"] == "Data Protection":
                if any(term in txt for term in ["consumer", "pii", "consent", "gdpr"]):
                    score += 20
            elif cp["policy"] == "Force Majeure":
                if any(term in txt for term in ["force majeure", "suspension"]):
                    score += 20
            elif cp["policy"] == "Audit Rights":
                if any(term in txt for term in ["audit", "inspect", "books"]):
                    score += 20

            status = "Compliant" if score >= 70 else "Partially" if score >= 40 else "Non-Compliant"
            compliance.append({
                "policy": cp["policy"],
                "status": status,
                "explanation": cp["rule"],
                "score": score,
                "evidence": snippet
            })

        violations = []
        risks_involved = []
        total_risks = []

        for vio in VIOLATION_POLICIES:
            res = semantic_search(query=vio["query"], top_k=2, contract_id=contract_id)
            docs = res.get("documents", [[]])
            snippet = docs[0][0] if docs and docs[0] else ""
            txt = snippet.lower()
            risk = 0

            if vio["policy"] == "Uncapped Liability":
                if any(x in txt for x in ["uncapped", "no cap", "no limit"]):
                    risk = 80
            elif vio["policy"] == "No Termination for Convenience":
                if "no convenience" in txt or ("termination" in txt and "convenience" not in txt):
                    risk = 60
            elif vio["policy"] == "Weak Confidentiality":
                if "less than one year" in txt or "weak" in txt:
                    risk = 55

            if risk >= vio["threshold"]:
                violations.append({
                    "policy": vio["policy"],
                    "severity": _risk_level(risk),
                    "explanation": vio["explain"],
                    "risk": risk,
                    "evidence": snippet
                })
                tag = vio.get("tag")
                if tag and tag not in risks_involved:
                    risks_involved.append(tag)
                total_risks.append(risk)

        # Calculate Risk Score
        clause_score = sum((100 - c["strength"]) for c in clauses if c["present"]) / max(len(clauses), 1)
        compliance_score = sum((100 - c["score"]) for c in compliance) / max(len(compliance), 1)
        violation_score = sum(total_risks) / max(len(total_risks), 1) if total_risks else 0
        risk_score = int(min(100, max(0, clause_score * 0.35 + compliance_score * 0.35 + violation_score * 0.3)))

        return {
            "contract_id": contract_id,
            "risk_score": risk_score,
            "risks_involved": risks_involved,
            "clauses": clauses,
            "compliance": compliance,
            "violations": violations
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
