from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import List
import uuid
import os
import shutil
from app.services.ocr import extract_text_from_image
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search, get_contract_chunks
from app.models.contract import ContractUploadResponse, SearchQuery, SearchResponse
from app.db.vector import chroma_manager
from pdfminer.high_level import extract_text

router = APIRouter(prefix="/contracts", tags=["contracts"])

# Local upload dir (optional backup)
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text using pdfminer."""
    return extract_text(file_path)

@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    """Upload and process a contract document"""
    try:
        contract_id = str(uuid.uuid4())
        file_ext = file.filename.lower().split(".")[-1]
        file_path = os.path.join(UPLOAD_DIR, f"{contract_id}.{file_ext}")

        # Save locally
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Extract text
        if file_ext == "pdf":
            text = extract_text_from_pdf(file_path)
        elif file_ext in ("png", "jpg", "jpeg", "tiff", "bmp"):
            text = extract_text_from_image(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")

        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document")

        # Chunk text
        chunks = chunk_text(text)

        # Embeddings
        embeddings = embed_chunks(chunks)

        # Store in Chroma
        doc_ids = store_embeddings(contract_id, chunks, embeddings)

        return ContractUploadResponse(
            contract_id=contract_id,
            filename=file.filename,
            chunks_processed=len(chunks),
            document_ids=doc_ids
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
