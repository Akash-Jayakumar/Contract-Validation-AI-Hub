from fastapi import APIRouter, File, UploadFile, Form, HTTPException
import uuid, os
from app.services.ocr import extract_text
from app.services.chunk import chunk_text
from app.services.embeddings import embed_chunks
from app.db.vector import add_embeddings
from app.db.mongo import save_contract_meta

router = APIRouter()

@router.post("/upload")
async def upload_contract(file: UploadFile = File(...), lang: str = Form("eng")):
    """Upload and process a contract file"""
    try:
        contract_id = str(uuid.uuid4())
        temp_path = f"/tmp/{contract_id}_{file.filename}"
        
        with open(temp_path, "wb") as f:
            f.write(await file.read())
        
        # Extract text using OCR
        text = extract_text(temp_path, lang=lang)
        
        # Chunk the text
        chunks = chunk_text(text)
        
        # Generate embeddings
        vectors = embed_chunks(chunks)
        
        # Prepare payloads
        payloads = [
            {"contract_id": contract_id, "chunk_id": i, "text": chunk} 
            for i, chunk in enumerate(chunks)
        ]
        
        # Store in vector database
        add_embeddings(vectors, payloads)
        
        # Save metadata
        save_contract_meta({
            "contract_id": contract_id,
            "filename": file.filename,
            "lang": lang,
            "chunks": len(chunks),
            "text_length": len(text)
        })
        
        # Clean up temp file
        os.remove(temp_path)
        
        return {
            "contract_id": contract_id,
            "chunks": len(chunks),
            "status": "stored in vectorDB"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {e}")

@router.get("/{contract_id}")
async def get_contract(contract_id: str):
    """Get contract metadata"""
    from app.db.mongo import get_contract_meta
    contract = get_contract_meta(contract_id)
    if not contract:
        raise HTTPException(status_code=404, detail="Contract not found")
    return contract
