from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any
from datetime import datetime
from app.services.embeddings import embed_chunks
from app.db.vector import chroma_manager

router = APIRouter()

# Clause definitions with expected checklist items
CLAUSE_LIBRARY = [
    {
        "id": "C1",
        "name": "Confidentiality Clause",
        "query": "confidentiality obligations nda survive termination",
        "items": [
            {"id": "I1", "description": "NDA terms clearly defined"},
            {"id": "I2", "description": "Covers employees & contractors"},
            {"id": "I3", "description": "Survives contract termination"},
        ],
    },
    {
        "id": "C2",
        "name": "Termination Clause",
        "query": "termination notice breach convenience",
        "items": [
            {"id": "I1", "description": "Termination notice period specified"},
            {"id": "I2", "description": "Termination for breach included"},
            {"id": "I3", "description": "Termination for convenience defined"},
        ],
    },
    {
        "id": "C3",
        "name": "Data Protection Clause",
        "query": "data protection gdpr privacy personal data",
        "items": [
            {"id": "I1", "description": "GDPR compliance mentioned"},
            {"id": "I2", "description": "Data retention policy defined"},
        ],
    },
]


def compliance_score(match_text: str, query: str) -> int:
    """Very simple scoring based on keyword hits."""
    if not match_text:
        return 0
    text = match_text.lower()
    score = 0
    for kw in query.split():
        if kw in text:
            score += 20
    return min(100, score)


def risk_level_from_score(score: int) -> str:
    if score >= 70:
        return "Low"
    elif score >= 40:
        return "Medium"
    return "High"


@router.post("/validate")
def validate_contract(payload: Dict[str, Any] = Body(...)):
    contract_id = payload.get("contract_id")
    if not contract_id:
        raise HTTPException(status_code=400, detail="contract_id is required")

    try:
        print(f"➡️ Starting validation for contract_id={contract_id}")
        clauses_out, risks_out, violations_out = [], [], []
        total_compliance = 0

        for clause in CLAUSE_LIBRARY:
            cid, cname, query, checklist = (
                clause["id"],
                clause["name"],
                clause["query"],
                clause["items"],
            )

            print(f"🔍 Processing clause: {cname} (ID={cid})")
            print(f"   ↳ Searching in vector DB with query: {query}")

            # Search in chroma db
            vec = embed_chunks([query])[0]
            res = chroma_manager.search_similar(
                query_embedding=vec, top_k=1, collection_name="contracts"
            )

            if res and res.get("documents") and res["documents"][0]:
                match_text = res["documents"][0][0]
                metadata = res.get("metadatas", [[{}]])[0][0]
                page_number = metadata.get("page_number")
                score = compliance_score(match_text, query)
                status = "present" if score > 0 else "missing"
                print(f"   ✅ Match found on page {page_number} with score={score}")
            else:
                match_text, page_number, score, status = "", None, 0, "missing"
                print("   ⚠️ No matching clause found in document")

            # Build clause output with checklist evaluation
            clause_items = []
            for item in checklist:
                if score >= 70:
                    item_status = "pass"
                elif score >= 40:
                    item_status = "partial"
                else:
                    item_status = "fail"

                clause_items.append(
                    {"id": item["id"], "description": item["description"], "status": item_status}
                )

            clauses_out.append(
                {
                    "id": cid,
                    "name": cname,
                    "status": status,
                    "page_number": page_number,
                    "compliance_score": score,
                    "items": clause_items,
                }
            )

            # Risks
            risk_score = int((100 - score) / 20) + 1
            risks_out.append(
                {
                    "clause_id": cid,
                    "page_number": page_number,
                    "risk_score": risk_score,
                    "risk_level": risk_level_from_score(score),
                    "description": f"{cname} evaluated with compliance score {score}.",
                }
            )

            # Violations
            if score <= 40:
                violations_out.append(
                    {
                        "id": f"V{len(violations_out)+1}",
                        "type": "Compliance",
                        "clause_id": cid,
                        "page_number": page_number,
                        "message": f"{cname} violation due to weak/missing compliance (score={score}).",
                    }
                )
                print(f"   ❌ Violation logged for {cname}")

            total_compliance += score

        # Overall scores
        overall_compliance_score = (
            int(total_compliance / len(CLAUSE_LIBRARY)) if CLAUSE_LIBRARY else 0
        )
        overall_risk_score = sum(r["risk_score"] for r in risks_out)
        overall_risk_level = (
            "High"
            if overall_compliance_score < 40
            else "Medium"
            if overall_compliance_score < 70
            else "Low"
        )
        overall_compliance_level = (
            "High"
            if overall_compliance_score >= 70
            else "Medium"
            if overall_compliance_score >= 40
            else "Low"
        )

        print("📊 Final Aggregated Results:")
        print(f"   ↳ Overall Compliance Score: {overall_compliance_score}")
        print(f"   ↳ Overall Risk Score: {overall_risk_score}")
        print(f"   ↳ Overall Risk Level: {overall_risk_level}")
        print(f"   ↳ Overall Compliance Level: {overall_compliance_level}")
        print("✅ Validation completed successfully")

        return {
            "contract_id": contract_id,
            "clauses": clauses_out,
            "risks": risks_out,
            "violations": violations_out,
            "overall_risk_score": overall_risk_score,
            "overall_risk_level": overall_risk_level,
            "overall_compliance_score": overall_compliance_score,
            "overall_compliance_level": overall_compliance_level,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    except Exception as e:
        print(f"🔥 Error while validating contract {contract_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
