from fastapi import APIRouter, HTTPException, Body
from typing import Dict, Any
import traceback
from app.services.compliance_highlighter import ComplianceHighlighter
from app.services.embeddings import get_contract_chunks
from app.routes.policies import auto_violation

router = APIRouter(prefix="/compliance", tags=["compliance"])

@router.post("/highlight-docx")
def highlight_docx(body: Dict[str, Any] = Body(...)):
    try:
        contract_id = body.get("contract_id")
        output_path = body.get("output_path")
        if not contract_id:
            raise HTTPException(status_code=400, detail="contract_id is required")

        # Get violation analysis
        violation_payload = auto_violation({"contract_id": contract_id})
        
        # Get contract chunks for highlighting
        results = get_contract_chunks(contract_id)
        docs = results.get("documents", [[]])
        chunks = docs[0] if docs and len(docs) > 0 else []
        
        if not chunks:
            raise HTTPException(status_code=400, detail="No chunks found for this contract_id")

        # Generate DOCX report
        highlighter = ComplianceHighlighter()
        report_path = highlighter.build_and_save(violation_payload, chunks, output_path)

        return {
            "report_path": report_path,
            "overall_risk": violation_payload.get("overall_risk", 0),
            "template_type": violation_payload.get("template_type", "unknown"),
            "version": violation_payload.get("version", "v1")
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")
