from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any
from pathlib import Path
import json, traceback

from app.services.embeddings import semantic_search
from app.services.llm import gemini_json, LLMJsonError

router = APIRouter(prefix="/policies", tags=["policies"])

# Constants for auto-violation
BROAD_K = 12
EACH_CLAUSE_K = 6
MAX_CONTEXT_CHARS = 8000
STANDARDS_DIR = Path("app/standards")

VIOLATION_SCHEMA = {
    "type": "object",
    "properties": {
        "violated": {"type": "boolean"},
        "risk": {"type": "integer"},
        "explanation": {"type": "string"},
        "evidence": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "chunk_index": {"type": "integer"},
                    "quote": {"type": "string"},
                    "span": {
                        "type": "object",
                        "properties": {"start": {"type": "integer"}, "end": {"type": "integer"}},
                        "required": ["start", "end"]
                    }
                },
                "required": ["chunk_index", "quote", "span"]
            }
        }
    },
    "required": ["violated", "risk", "explanation", "evidence"]
}

SYSTEM_HEADER = (
    "You are an expert contracts reviewer comparing third‑party paper to our internal standard template/playbook. "
    "Use ONLY the provided excerpts. If evidence is insufficient, return violated=false with a low risk and explain why. "
    "Never fabricate quotes; quotes must be copied verbatim from the provided text."
)

def _load_playbook(template_type: str) -> Dict[str, Any]:
    fn = STANDARDS_DIR / f"{template_type.lower()}_playbook.json"
    if not fn.exists():
        raise FileNotFoundError(f"Playbook not found for template: {template_type} at {fn}")
    return json.loads(fn.read_text(encoding="utf-8"))

def _classify_template(chunks: List[str]) -> str:
    text = " ".join(chunks[:5]).lower()
    if "non-disclosure" in text or "non disclosure" in text or "confidential" in text:
        return "nda"
    if "statement of work" in text or "sow" in text:
        return "sow"
    return "msa"

def _build_compare_prompt(clause: Dict[str, Any], evidences: List[Dict[str, Any]]) -> str:
    preferred = clause.get("preferred", "")
    fallbacks = clause.get("fallbacks", [])
    fall_str = "\n- ".join(fallbacks) if fallbacks else "(none)"

    text_blocks, total = [], 0
    for ev in evidences:
        text = ev["text"] or ""
        remain = MAX_CONTEXT_CHARS - total
        if remain <= 0:
            break
        snippet = text[:remain]
        text_blocks.append(f"[chunk_index={ev['chunk_index']}]\n{snippet}")
        total += len(snippet)

    context = "\n\n---\n\n".join(text_blocks)

    return f"""
{SYSTEM_HEADER}

Standard Clause (Preferred):
{preferred}

Acceptable Fallbacks:
- {fall_str}

Task:
Compare the contract excerpts to the preferred language and acceptable fallbacks.
Decide if the contract VIOLATES our standard. If violated, assign risk 0–100 (higher = riskier), explain why,
and cite precise quotes with character spans relative to each chunk.

Return STRICT JSON in this exact shape:
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

Contract Excerpts (these are the ONLY sources you may cite):
{context}
"""

def _overall_risk(items: List[Dict[str, Any]]) -> int:
    risks = [it.get("risk", 0) for it in items if it.get("violated")]
    if not risks:
        return 0
    return int(round(sum(risks) / len(risks)))

@router.post("/auto-violation")
def auto_violation(body: Dict[str, Any] = Body(...)):
    try:
        contract_id = body.get("contract_id")
        if not contract_id:
            raise HTTPException(status_code=400, detail="contract_id is required")

        # Retrieve coarse context for classification
        broad = semantic_search(query="contract type and general clauses", top_k=BROAD_K, contract_id=contract_id)
        docs = broad.get("documents", [[]])
        chunks = docs[0] if docs and len(docs) > 0 else []
        if not chunks:
            return {
                "contract_id": contract_id,
                "template_type": "unknown",
                "version": "unknown",
                "overall_risk": 100,
                "violations": [],
                "note": "No content retrieved for this contract; defaulting to high risk."
            }

        template_type = _classify_template(chunks)
        playbook = _load_playbook(template_type)
        clauses = playbook.get("clauses", [])
        results: List[Dict[str, Any]] = []

        for cl in clauses:
            title = cl.get("title", "")
            keywords = cl.get("keywords", [])
            q = (title + " " + " ".join(keywords)).strip() or title or "key clause"

            sr = semantic_search(query=q, top_k=EACH_CLAUSE_K, contract_id=contract_id)
            d2 = sr.get("documents", [[]])
            m2 = sr.get("metadatas", [[]])
            c2 = d2[0] if d2 and len(d2) > 0 else []
            meta2 = m2[0] if m2 and len(m2) > 0 else []

            evidence_blocks = []
            for i, text in enumerate(c2):
                md = meta2[i] if i < len(meta2) else {}
                evidence_blocks.append({"chunk_index": md.get("chunk_index", i), "text": text or ""})

            prompt = _build_compare_prompt(cl, evidence_blocks)
            decision = gemini_json(prompt, response_schema=VIOLATION_SCHEMA)

            normalized_ev = []
            for ev in decision.get("evidence", []):
                try:
                    normalized_ev.append({
                        "chunk_index": int(ev.get("chunk_index")),
                        "quote": str(ev.get("quote", ""))[:1000],
                        "span": {
                            "start": max(0, int(ev.get("span", {}).get("start", 0))),
                            "end": max(0, int(ev.get("span", {}).get("end", 0))),
                        }
                    })
                except Exception:
                    continue

            results.append({
                "policy_id": cl.get("id"),
                "title": cl.get("title"),
                "violated": bool(decision.get("violated", False)),
                "risk": int(decision.get("risk", 0)),
                "explanation": str(decision.get("explanation", ""))[:1000],
                "evidence": normalized_ev
            })

        return {
            "contract_id": contract_id,
            "template_type": playbook.get("template_type", template_type.upper()),
            "version": playbook.get("version", "v1"),
            "overall_risk": _overall_risk(results),
            "violations": results
        }
    except HTTPException:
        raise
    except LLMJsonError as e:
        raise HTTPException(status_code=500, detail=f"LLM JSON parsing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")

# Keep the existing violation endpoint for backward compatibility
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
            results = semantic_search(query=rule, top_k=EACH_CLAUSE_K, contract_id=contract_id)
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

            separator = '\n\n---\n\n'
            evidence_texts = [f'[chunk_index={ev["chunk_index"]}]\n{ev["text"]}' for ev in evidences]
            context = separator.join(evidence_texts)
            
            prompt = f"""{SYSTEM_HEADER}

POLICY RULE:
{rule}

CONTRACT EXCERPTS:
{context}

Output strict JSON with this shape:
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
}}"""
            
            decision = gemini_json(prompt, response_schema=VIOLATION_SCHEMA)

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

        overall = _overall_risk(out)
        return {
            "contract_id": contract_id,
            "overall_risk": overall,
            "overall_explanation": "Average of risks for violated policies",
            "violations": out
        }
    except HTTPException:
        raise
    except LLMJsonError as e:
        raise HTTPException(status_code=500, detail=f"LLM JSON parsing error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{e}\n{traceback.format_exc()}")
