from fastapi import APIRouter, File, UploadFile, HTTPException, Body
from typing import List, Optional
import uuid
import os
import shutil
from app.services.ocr import extract_text_from_pdf, extract_text_from_image
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks, store_embeddings, semantic_search, get_contract_chunks
from app.models.contract import ContractUploadResponse, SearchQuery, SearchResponse
from app.db.vector import chroma_manager

router = APIRouter(prefix="/contracts", tags=["contracts"])

# Define a local upload directory inside your project
UPLOAD_DIR = os.path.join(os.getcwd(), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload", response_model=ContractUploadResponse)
async def upload_contract(file: UploadFile = File(...)):
    """Upload and process a contract document"""
    try:
        contract_id = str(uuid.uuid4())
        file_path = os.path.join(UPLOAD_DIR, f"{contract_id}_{file.filename}")
        
        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Extract text based on file type
        if file.filename.lower().endswith('.pdf'):
            text = extract_text_from_pdf(file_path)
        elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp')):
            text = extract_text_from_image(file_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file type")
        
        if not text.strip():
            raise HTTPException(status_code=400, detail="Could not extract text from document")
        
        # Chunk text
        chunks = chunk_text(text)
        
        # Generate embeddings
        embeddings = embed_chunks(chunks)
        
        # Store in ChromaDB
        doc_ids = store_embeddings(contract_id, chunks, embeddings)
        
        return ContractUploadResponse(
            contract_id=contract_id,
            filename=file.filename,
            chunks_processed=len(chunks),
            document_ids=doc_ids
        )
        
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

<<<<<<< HEAD
<<<<<<< HEAD
=======
=======
>>>>>>> ca11abee71761f70fb4c22b05dea0a54f1471535
from app.db.vector import chroma_manager

>>>>>>> ca11abee71761f70fb4c22b05dea0a54f1471535
@router.get("/{contract_id}/info")
async def get_contract_info(contract_id: str):
    """Get contract information"""
    try:
<<<<<<< HEAD
<<<<<<< HEAD
        count = chroma_manager.get_collection_count("contracts")
=======
=======
>>>>>>> ca11abee71761f70fb4c22b05dea0a54f1471535
        # Get count for this specific contract
        results = chroma_manager.search_similar(
            query_embedding=[0.0] * 384,  # Dummy embedding, we just want to use where clause
            top_k=1000,
            where={"contract_id": contract_id}
        )
        
        chunk_count = len(results["documents"][0]) if results["documents"] and results["documents"][0] else 0
        
<<<<<<< HEAD
>>>>>>> ca11abee71761f70fb4c22b05dea0a54f1471535
=======
>>>>>>> ca11abee71761f70fb4c22b05dea0a54f1471535
        return {
            "contract_id": contract_id,
            "chunk_count": chunk_count,
            "total_documents_in_db": chroma_manager.get_collection_count()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
