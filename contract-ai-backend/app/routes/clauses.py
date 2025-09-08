from fastapi import APIRouter, Body, HTTPException, UploadFile, File
from typing import List, Dict, Any, Union
import uuid
import json

from app.db.vector import chroma_manager  # wrapper over chromadb client (HttpClient/PersistentClient)
from app.services.embeddings import embed_chunks  # returns List[List[float]]

router = APIRouter(tags=["clauses"])
LIB_COLLECTION = "standard_clauses"

def _validate_clause(it: Dict[str, Any]):
    for f in ("title", "category", "text"):
        if not it.get(f) or not str(it.get(f)).strip():
            raise HTTPException(status_code=400, detail=f"Missing or empty field: {f}")

def _build_metadata(it: Dict[str, Any], clause_id: str) -> Dict[str, Any]:
    def scalar(v):
        # Chroma accepts only str|int|float|bool|None; convert others to JSON strings
        if isinstance(v, (str, int, float, bool)) or v is None:
            return v
        # For lists/dicts, join or json-dump; prefer compact CSV for lists you will filter on
        if isinstance(v, list):
            # join as CSV for simple tags; adjust delimiter if needed
            return ",".join([str(x) for x in v])
        return json.dumps(v, ensure_ascii=False)

    return {
        "clause_id": clause_id,
        "title": scalar(it.get("title")),
        "category": scalar(it.get("category")),
        "source": scalar(it.get("source")),
        "version": scalar(it.get("version")),
        "jurisdiction": scalar(it.get("jurisdiction")),
        "tags": scalar(it.get("tags")),  # list -> "delaware,venue"
    }

@router.post("/upload-json")
def upload_standard_clauses(payload: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(..., embed=False)):
    """
    Upload standard template clauses as JSON and store in ChromaDB.
    Accepts a single object or a list of objects.
    Required per clause: title, category, text
    Optional: source, version, jurisdiction, tags[]
    """
    # Normalize to list
    items: List[Dict[str, Any]] = payload if isinstance(payload, list) else [payload]
    if not items:
        raise HTTPException(status_code=400, detail="Empty JSON")

    texts = [it["text"] for it in items]
    # Validate and prepare
    for it in items:
        _validate_clause(it)

    ids = [it.get("clause_id") or str(uuid.uuid4()) for it in items]
    metadatas = [_build_metadata(it, ids[i]) for i, it in enumerate(items)]

    # Pre-check metadata for scalar values
    for md in metadatas:
        for k, v in md.items():
            if not isinstance(v, (str, int, float, bool)) and v is not None:
                raise HTTPException(status_code=400, detail=f"Metadata field '{k}' must be scalar; got {type(v).__name__}")

    # Embed and add to Chroma collection
    try:
        embs = embed_chunks(texts)
        chroma_manager.get_or_create_collection(LIB_COLLECTION)  # idempotent
        chroma_manager.add_documents(
            documents=texts,
            embeddings=embs,
            metadatas=metadatas,
            ids=ids,
            collection_name=LIB_COLLECTION,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chroma store failed: {e}")

    return {"status": "stored", "collection": LIB_COLLECTION, "count": len(ids), "ids": ids}

@router.get("/")
def list_clauses(category: str | None = None, limit: int = 100, offset: int = 0):
    where = {"category": category} if category else None
    res = chroma_manager.get_documents(collection_name=LIB_COLLECTION, include=["ids", "documents", "metadatas"], where=where, limit=limit, offset=offset)

    out = []
    docs = res.get("documents") or []
    metas = res.get("metadatas") or []
    ids = res.get("ids") or []
    for doc, md, id_ in zip(docs, metas, ids):
        out.append({"clause_id": id_, "title": (md or {}).get("title") or "", "category": (md or {}).get("category") or "", "text": doc})
    return {"count": len(out), "clauses": out}

@router.put("/{clause_id}")
def update_clause(clause_id: str, payload: Dict[str, Any] = Body(...)):
    docs = [payload["text"]] if payload.get("text") else None
    embs = embed_chunks([payload["text"]]) if payload.get("text") else None
    md = _build_metadata(payload, clause_id)
    chroma_manager.update_documents(
        collection_name=LIB_COLLECTION,
        ids=[clause_id],
        documents=docs,
        embeddings=embs,
        metadatas=[md],
    )
    return {"status": "updated", "clause_id": clause_id}

@router.delete("/{clause_id}")
def delete_clause(clause_id: str):
    chroma_manager.delete_documents(collection_name=LIB_COLLECTION, ids=[clause_id])
    return {"status": "deleted", "clause_id": clause_id}

def _normalize_scalar(v: Any) -> Any:
    # Chroma metadata must be str|int|float|bool|None
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    if isinstance(v, list):
        # keep a simple CSV string for readability
        return ",".join(str(x) for x in v)
    try:
        return json.dumps(v, ensure_ascii=False)
    except Exception:
        return str(v)

def _mk_metadata(it: Dict[str, Any], clause_id: str) -> Dict[str, Any]:
    # keep minimal, scalar-safe metadata
    return {
        "clause_id": clause_id,
        "title": _normalize_scalar(it.get("title") or ""),
        "category": _normalize_scalar(it.get("category") or ""),
        "version": _normalize_scalar(it.get("version") or ""),
        "jurisdiction": _normalize_scalar(it.get("jurisdiction") or ""),
        "source": _normalize_scalar(it.get("source") or "STD-DOC"),
        "tags": _normalize_scalar(it.get("tags") or []),
    }

@router.post("/upload-standard-document")
async def upload_standard_document(file: UploadFile = File(...)):
    """
    Upload a standard template document (JSON file). Accepts:
    - A JSON file containing a single clause object {title, category, text, ...}, or
    - A list of clause objects [{...}, ...]
    Only 'text' fields are embedded and stored as Chroma documents.
    Minimal scalar metadata (title, category, clause_id, etc.) is stored for filtering.
    """
    content = await file.read()
    try:
        document = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    items: List[Dict[str, Any]] = document if isinstance(document, list) else [document]
    if not items:
        raise HTTPException(status_code=400, detail="Empty JSON")

    # Validate and gather texts
    texts: List[str] = []
    ids: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    for it in items:
        title = (it.get("title") or "").strip()
        category = (it.get("category") or "").strip()
        text = (it.get("text") or "").strip()
        if not text:
            raise HTTPException(status_code=400, detail="Each clause must include non-empty 'text'")
        if not title or not category:
            # still allow, but warn via metadata
            pass
        clause_id = str(it.get("clause_id") or uuid.uuid4())
        ids.append(clause_id)
        texts.append(text)
        metadatas.append(_mk_metadata(it, clause_id))

    # Embed and add to Chroma; store ONLY the text as document
    try:
        chroma_manager.get_or_create_collection(LIB_COLLECTION)
        embeddings = embed_chunks(texts)
        chroma_manager.add_documents(
            collection_name=LIB_COLLECTION,
            documents=texts,         # text only
            embeddings=embeddings,   # vectors of texts
            metadatas=metadatas,     # scalar-safe metadata
            ids=ids
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chroma store failed: {e}")

    return {
        "status": "stored",
        "collection": LIB_COLLECTION,
        "count": len(ids),
        "ids": ids
    }
