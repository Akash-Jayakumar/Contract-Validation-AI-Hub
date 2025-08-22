from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import os
import shutil
from app.services.ocr import extract_text
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search, get_contract_chunks
from app.models.contract import ContractUploadResponse, SearchQuery, SearchResponse

router = APIRouter(prefix="/contracts", tags=["contracts"])

UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    """Upload and process a contract document"""
    contract_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{contract_id}_{file.filename}")
    try:
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"File save error: {e}")

    # Extract text based on file type
    try:
        if file.filename.lower().endswith(('.pdf', '.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            try:
                text = extract_text(file_path)
            except Exception as e:
                # Specific handling for poppler/pdf2image errors
                if "Unable to get page count" in str(e) or "poppler" in str(e).lower():
                    raise HTTPException(
                        status_code=500,
                        detail="PDF/image extraction failed: Poppler may not be installed, or in PATH, or your system requires a restart. See https://github.com/oschwartz10612/poppler-windows/releases/ and ensure C:/poppler/bin is in your PATH."
                    )
                else:
                    raise HTTPException(status_code=500, detail=f"OCR/text extraction error: {e}")
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document")
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected extraction error: {e}")

    # Chunk and embed
    try:
        chunks = chunk_text(text)
        embeddings = embed_chunks(chunks)
        doc_ids = store_embeddings(contract_id, chunks, embeddings)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunk/embed/index error: {e}")

    return ContractUploadResponse(
        contract_id=contract_id,
        filename=file.filename,
        chunks_processed=len(chunks),
        document_ids=doc_ids
    )

@router.post("/search", response_model=SearchResponse)
async def semantic_search_endpoint(query: SearchQuery = Body(...)):
    """Semantic search across contracts"""
    try:
        results = semantic_search(
            query=query.text,
            top_k=query.top_k or 5,
            contract_id=query.contract_id
        )
        
        # Format results
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for i, (doc, metadata, distance) in enumerate(zip(
                results['documents'][0],
                results['metadatas'][0],
                results['distances'][0]
            )):
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
        
        formatted_results = []
        if results['documents'] and results['documents'][0]:
            for doc, metadata in zip(results['documents'][0], results['metadatas'][0]):
                formatted_results.append({
                    "text": doc,
                    "chunk_index": metadata.get("chunk_index")
                })
        
        return {"contract_id": contract_id, "chunks": formatted_results}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from app.db.vector import chroma_manager

@router.get("/{contract_id}/info")
async def get_contract_info(contract_id: str):
    """Get contract information"""
    try:
        # Get count for this specific contract
        results = chroma_manager.search_similar(
            query_embedding=[0.0] * 384,  # Dummy embedding, we just want to use where clause
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
