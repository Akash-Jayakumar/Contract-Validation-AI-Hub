from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import List
import uuid
import os
import shutil
from app.services.ocr import extract_text_from_image
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search, get_contract_chunks
from app.services.pdf_pages import extract_pages_text
from app.services.sectioner import section_text_with_pages
from app.models.contract import ContractUploadResponse, SearchQuery, SearchResponse
from app.db.vector import chroma_manager
from pdfminer.high_level import extract_text

router = APIRouter(prefix="/contracts", tags=["contracts"])

# Local upload dir (optional backup)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...)):
    from fastapi import HTTPException
    import uuid, os, shutil
    from app.services.ocr import extract_text_from_image
    from app.services.embeddings import embed_chunks, store_embeddings
    from app.services.chunk import chunk_text
    try:
        from app.services.sectioner import section_text_with_pages
        HAVE_PAGES = True
    except Exception:
        HAVE_PAGES = False
    try:
        from app.services.pdf_pages import extract_pages_text
        HAVE_PAGE_EXTRACT = True
    except Exception:
        HAVE_PAGE_EXTRACT = False

    try:
        contract_id = str(uuid.uuid4())
        filename = file.filename or "document"
        file_ext = filename.lower().split(".")[-1]
        if not file_ext:
            raise HTTPException(status_code=400, detail="File must have an extension")

        dest_path = os.path.join(UPLOAD_DIR, f"{contract_id}.{file_ext}")

        # Save file
        with open(dest_path, "wb") as buf:
            shutil.copyfileobj(file.file, buf)

        # 1) Extract text (and pages if available)
        raw_text = ""
        sections = []
        titles = []
        page_starts = []
        page_ends = []

        if file_ext == "pdf":
            if HAVE_PAGES and HAVE_PAGE_EXTRACT:
                # Page-aware pipeline
                pages = extract_pages_text(dest_path)  # [(pno, text)]
                if not pages or all(not ptxt.strip() for _, ptxt in pages):
                    raise HTTPException(status_code=400, detail="No text extracted from PDF pages")
                sec_objs = section_text_with_pages(pages)
                if not sec_objs:
                    raise HTTPException(status_code=400, detail="Could not segment PDF into sections")
                sections = [s["text"] for s in sec_objs]
                titles = [s["title"] for s in sec_objs]
                page_starts = [s["page_start"] for s in sec_objs]
                page_ends = [s["page_end"] for s in sec_objs]
            else:
                # Simple extraction + sectioning
                from pdfminer.high_level import extract_text as pdf_extract_text
                raw_text = pdf_extract_text(dest_path) or ""
                if not raw_text.strip():
                    raise HTTPException(status_code=400, detail="Could not extract text from PDF")
                sec_objs = chunk_text(raw_text)
                if not sec_objs:
                    raise HTTPException(status_code=400, detail="Could not segment PDF into sections")
                # section_text returns list[dict] with {"title","text"} if using the new function
                # or list[str] if using legacy; normalize both
                if isinstance(sec_objs, list) and sec_objs and isinstance(sec_objs[0], dict):
                    sections = [s["text"] for s in sec_objs]
                    titles = [s["title"] for s in sec_objs]
                else:
                    sections = list(sec_objs)
                    titles = ["" for _ in sections]
        elif file_ext in ("png", "jpg", "jpeg", "tiff", "bmp"):
            raw_text = extract_text_from_image(dest_path)
            if not raw_text.strip():
                raise HTTPException(status_code=400, detail="Could not extract text from image")
            sec_objs = chunk_text(raw_text)
            if not sec_objs:
                raise HTTPException(status_code=400, detail="Could not segment image text into sections")
            if isinstance(sec_objs, list) and sec_objs and isinstance(sec_objs[0], dict):
                sections = [s["text"] for s in sec_objs]
                titles = [s["title"] for s in sec_objs]
            else:
                sections = list(sec_objs)
                titles = ["" for _ in sections]
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        if not sections:
            raise HTTPException(status_code=400, detail="No content sections produced from document")

        # Sanity check and fix swapped title/body
        fixed_bodies = []
        fixed_titles = []
        for i, (t, b) in enumerate(zip(titles, sections)):
            tt = (t or "").strip()
            bb = (b or "").strip()
            if not bb and tt and len(tt) > 200:
                # Treat this as a mis-detected header; move text into body and shorten title
                bb = tt
                tt = tt[:160].rstrip(" ,;:.-") + "…"
            if not tt:
                # Fallback: first 160 chars of body as title
                tmp = " ".join(bb.split())
                tt = (tmp[:160].rstrip(" ,;:.-") + "…") if tmp else "Untitled"
            # Truncate title to 160 chars
            if len(tt) > 160:
                tt = tt[:160].rstrip(" ,;:.-") + "…"
            fixed_bodies.append(bb)
            fixed_titles.append(tt)

        # Ensure no empty document bodies
        assert all(isinstance(d, str) and d.strip() != "" for d in fixed_bodies), "Empty document body detected"

        # 2) Embeddings
        try:
            embeddings = embed_chunks(fixed_bodies)
        except Exception as ee:
            raise HTTPException(status_code=500, detail=f"Embedding failed: {ee}")

        # 3) Store with metadata (including pages if available)
        metadatas = []
        for i in range(len(fixed_bodies)):
            md = {"contract_id": contract_id, "chunk_index": i, "title": fixed_titles[i]}
            if page_starts and page_ends and i < len(page_starts):
                md["page_start"] = page_starts[i]
                md["page_end"] = page_ends[i]
            metadatas.append(md)

        try:
            store_embeddings(contract_id, fixed_bodies, embeddings, metadatas=metadatas)
        except TypeError:
            # Backward compatibility with older store_embeddings(signature with titles)
            store_embeddings(contract_id, fixed_bodies, embeddings, titles=fixed_titles)

        return {
            "contract_id": contract_id,
            "filename": filename,
            "chunks_processed": len(sections),
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search", response_model=SearchResponse)
async def semantic_search_endpoint(query: SearchQuery = Body(...)):
    """Semantic search across contracts"""
    try:
        results = semantic_search(
            query=query.text,
            top_k=query.top_k or 5,
            contract_id=query.contract_id
        )

        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for doc, metadata, distance in zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            ):
                formatted_results.append({
                    "text": doc,
                    "contract_id": metadata.get("contract_id"),
                    "chunk_index": metadata.get("chunk_index"),
                    "score": 1 - distance
                })

        return SearchResponse(
            query=query.text,
            results=formatted_results,
            total_results=len(formatted_results)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contract_id}/chunks")
async def get_contract_chunks_endpoint(contract_id: str):
    """Get all chunks for a specific contract"""
    try:
        results = get_contract_chunks(contract_id)

        # Validate type early
        if not isinstance(results, dict):
            raise HTTPException(status_code=500, detail="Chunks backend returned invalid type (expected dict)")

        documents = results.get("documents")
        metadatas = results.get("metadatas")

        if not documents or not documents[0] or not metadatas or not metadatas[0]:
            return {"contract_id": contract_id, "chunks": []}

        docs = documents[0]
        metas = metadatas[0]

        formatted = []
        for doc, md in zip(docs, metas):
            md = md or {}
            formatted.append({
                "title": md.get("title") or "",
                "text": doc,
                "chunk_index": md.get("chunk_index"),
                "page_start": md.get("page_start"),
                "page_end": md.get("page_end"),
            })

        return {"contract_id": contract_id, "chunks": formatted}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{contract_id}/info")
async def get_contract_info(contract_id: str):
    """Get contract information"""
    try:
        results = chroma_manager.search_similar(
            query_embedding=[0.0] * 384,  # dummy embedding
            top_k=1000,
            where={"contract_id": contract_id}
        )

        chunk_count = len(results["documents"][0]) if results["documents"] and results["documents"][0] else 0

        return {
            "contract_id": contract_id,
            "chunk_count": chunk_count,
            "total_documents_in_db": chroma_manager.get_collection_count()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
