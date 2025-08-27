from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from app.services.embeddings import semantic_search
from app.services.llm import gemini_json, LLMJsonError
import math
import traceback

router = APIRouter(prefix="/policies", tags=["policies"])

# Internal retrieval controls
EACH_POLICY_K = 6  # evidence candidates per policy
MAX_CONTEXT_CHARS = 8000  # keep prompt under model limits

VIOLATION_SYSTEM = """
You are a senior contracts compliance analyst.
Given (1) a policy rule and (2) retrieved contract excerpts, decide if the policy is violated.
If violated, return a short explanation, risk (0-100), and quote specific evidence.
If not violated, set violated=false and risk near 0 with rationale.
Return spans as character offsets relative to the provided chunk text so a UI can highlight them.
Be strict but practical; prefer false negatives over hallucinations.
Use only the provided contract excerpts for evidence.
"""

def build_policy_prompt(rule: str, evidences: List[Dict[str, Any]]) -> str:
    # Flatten evidences into numbered blocks for precise references
    blocks = []
    total = 0
    for ev in evidences:
        idx = ev.get("chunk_index")
        text = ev.get("text", "")
        # trim to keep within limit
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

CONTRACT EXCERPTS (multiple chunks, each has chunk_index):
{context}

Output strict JSON with this shape:
{{
  "violated": bool,
  "risk": int,  // 0-100
  "explanation": str,
  "evidence": [
    {{
      "chunk_index": int,
      "quote": str,
      "span": {{"start": int, "end": int}}
    }}
  ]
}}
Ensure quote is copied verbatim from the corresponding chunk text and span indices match the quote positions.
If no evidence, return an empty list and set violated=false.
"""

def weighted_overall(violations: List[Dict[str, Any]]) -> int:
    if not violations:
        return 0
    # Simple mean of risks for violated policies; tune as needed
    risky = [v.get("risk", 0) for v in violations if v.get("violated")]
    if not risky:
        return 0
    return int(round(sum(risky) / len(risky)))

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

            # Retrieve likely evidence per policy
            results = semantic_search(query=rule, top_k=EACH_POLICY_K, contract_id=contract_id)
            documents = results.get("documents", [[]])
            metadatas = results.get("metadatas", [[]])
            chunks = documents[0] if documents and len(documents) > 0 else []
            metadata_list = metadatas[0] if metadatas and len(metadatas) > 0 else []

            # Build LLM inputs with chunk_index and text
            evidences = []
            for i, text in enumerate(chunks):
                md = metadata_list[i] if i < len(metadata_list) else {}
                evidences.append({
                    "chunk_index": md.get("chunk_index", i),
                    "text": text or ""
                })

            prompt = build_policy_prompt(rule, evidences)
            decision = gemini_json(prompt)  # returns dict with violated, risk, explanation, evidence[]

            # Sanitize evidence to include only allowed fields
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
        return {
            "contract_id": contract_id,
            "overall_risk": overall,
            "overall_explanation": "Average of risks for violated policies; tune weights as needed.",
            "violations": out
        }
    except HTTPException:
        raise
    except LLMJsonError as e:
        raise HTTPException(status_code=500, detail=f"LLM JSON parsing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")
