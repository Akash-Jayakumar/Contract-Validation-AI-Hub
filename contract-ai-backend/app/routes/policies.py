from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from app.services.embeddings import semantic_search
from app.services.llm import gemini_json, LLMJsonError
import traceback
import boto3
try:
    import fitz  # PyMuPDF
    HAVE_FITZ = hasattr(fitz, "open")
except Exception:
    fitz = None
    HAVE_FITZ = False

router = APIRouter(prefix="/policies", tags=["policies"])

# Retrieval
EACH_POLICY_K = 6
MAX_CONTEXT_CHARS = 8000

# S3
S3_BUCKET = "exo-cat"
s3_client = boto3.client("s3", region_name="ap-south-1")

VIOLATION_SYSTEM = """
You are a senior contracts compliance analyst.
Given (1) a policy rule and (2) retrieved contract excerpts, decide if the policy is violated.
If violated, return a short explanation, risk (0-100), and quote specific evidence.
⚠️ IMPORTANT: If violated=true, always include at least one evidence item.
If you cannot find an exact clause, select the closest excerpt.
Never leave evidence empty when violated=true.
If not violated, set violated=false and risk near 0 with rationale.
Return spans as character offsets relative to the provided chunk text.
"""

# ---------- Prompt builder ----------
def build_policy_prompt(rule: str, evidences: List[Dict[str, Any]]) -> str:
    blocks, total = [], 0
    for ev in evidences:
        idx = ev.get("chunk_index")
        text = ev.get("text", "")
        remain = MAX_CONTEXT_CHARS - total
        if remain <= 0:
            break
        snippet = text[:remain]
        total += len(snippet)
        blocks.append(f"[chunk_index={idx}]\n{snippet}")
    context = "\n\n---\n\n".join(blocks)

    return f"""{VIOLATION_SYSTEM}

POLICY RULE:
{rule}

CONTRACT EXCERPTS:
{context}

Output strict JSON:
{{
  "violated": bool,
  "risk": int,
  "explanation": str,
  "evidence": [
    {{
      "chunk_index": int,
      "quote": str,
      "span": {{"start": int, "end": int}}
    }}
  ]
}}
"""
def auto_violation(contract_text: str):
    """
    Dummy implementation of auto_violation.
    Replace with your real violation detection logic.
    """
    return [
        {
            "id": "V1",
            "type": "Compliance",
            "clause_id": "C3",
            "message": "GDPR compliance violation due to missing Data Protection Clause."
        }
    ]

# ---------- Risk calculator ----------
def weighted_overall(violations: List[Dict[str, Any]]) -> int:
    risky = [v.get("risk", 0) for v in violations if v.get("violated")]
    return int(round(sum(risky) / len(risky))) if risky else 0

# ---------- PDF highlighter ----------
def highlight_pdf(pdf_path: str, violations: list, output_path: str):
    if not HAVE_FITZ:
        # If fitz is not available, just copy the file without highlighting
        import shutil
        shutil.copy(pdf_path, output_path)
        return output_path

    doc = fitz.open(pdf_path)
    for v in violations:
        if not v.get("violated"):
            continue
        for ev in v.get("evidence", []):
            quote = ev.get("quote", "").strip()
            if not quote:
                continue
            for page in doc:
                areas = page.search_for(quote)
                for area in areas:
                    annot = page.add_highlight_annot(area)
                    annot.update()
    doc.save(output_path)
    return output_path

# ---------- Main API ----------
@router.post("/violation")
def check_policy_violation(payload: Dict[str, Any] = Body(...)):
    try:
        contract_id = payload.get("contract_id")
        policies = payload.get("policies") or []
        if not contract_id:
            raise HTTPException(status_code=400, detail="contract_id is required")
        if not isinstance(policies, list) or not policies:
            raise HTTPException(status_code=400, detail="policies must be a non-empty list")

        out = []
        for pol in policies:
            pid = pol.get("id") or pol.get("policy_id") or "POLICY"
            title = pol.get("title") or pid
            rule = pol.get("rule") or pol.get("description")
            if not rule:
                out.append({
                    "policy_id": pid, "title": title, "violated": False,
                    "risk": 0, "explanation": "No rule provided", "evidence": []
                })
                continue

            results = semantic_search(query=rule, top_k=EACH_POLICY_K, contract_id=contract_id)
            documents = results.get("documents", [[]])
            metadatas = results.get("metadatas", [[]])
            chunks = documents[0] if documents else []
            metadata_list = metadatas[0] if metadatas else []

            evidences = []
            for i, text in enumerate(chunks):
                md = metadata_list[i] if i < len(metadata_list) else {}
                evidences.append({
                    "chunk_index": md.get("chunk_index", i),
                    "text": text or ""
                })

            prompt = build_policy_prompt(rule, evidences)
            decision = gemini_json(prompt)

            if decision.get("violated", False) and not decision.get("evidence"):
                if evidences:
                    best_ev = evidences[0]
                    snippet = best_ev.get("text", "")[:500]
                    decision["evidence"] = [{
                        "chunk_index": best_ev.get("chunk_index", 0),
                        "quote": snippet,
                        "span": {"start": 0, "end": len(snippet)}
                    }]

            ev_out = []
            for ev in decision.get("evidence", []):
                try:
                    ev_out.append({
                        "chunk_index": int(ev.get("chunk_index")),
                        "quote": str(ev.get("quote", ""))[:1000],
                        "span": {
                            "start": max(0, int(ev.get("span", {}).get("start", 0))),
                            "end": max(0, int(ev.get("span", {}).get("end", 0)))
                        }
                    })
                except Exception:
                    continue

            out.append({
                "policy_id": pid,
                "title": title,
                "violated": bool(decision.get("violated", False)),
                "risk": int(decision.get("risk", 0)),
                "explanation": str(decision.get("explanation", ""))[:1000],
                "evidence": ev_out
            })

        overall = weighted_overall(out)

        # ==== Highlight + Upload to S3 ====
        local_path = f"/tmp/{contract_id}.pdf"
        highlighted_path = f"/tmp/{contract_id}_highlighted.pdf"
        s3_key = f"contracts/{contract_id}.pdf"
        s3_key_highlighted = f"contracts/{contract_id}_highlighted.pdf"

        s3_client.download_file(S3_BUCKET, s3_key, local_path)
        highlight_pdf(local_path, out, highlighted_path)
        s3_client.upload_file(highlighted_path, S3_BUCKET, s3_key_highlighted)

        highlighted_url = f"https://{S3_BUCKET}.s3.ap-south-1.amazonaws.com/{s3_key_highlighted}"

        return {
            "contract_id": contract_id,
            "overall_risk": overall,
            "overall_explanation": "Average of risks for violated policies.",
            "violations": out,
            "highlighted_pdf_url": highlighted_url
        }

    except HTTPException:
        raise
    except LLMJsonError as e:
        raise HTTPException(status_code=500, detail=f"LLM JSON parsing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")
