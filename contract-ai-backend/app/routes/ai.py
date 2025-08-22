from fastapi import APIRouter, HTTPException, UploadFile, File
from app.services.llm import gemini_flash_complete
from app.services.ocr import extract_text
import tempfile
import os

router = APIRouter()

@router.post("/analyze")
async def ai_analyze(file: UploadFile = File(...)):
    """Analyze contract using AI for financial health and risk assessment"""
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Extract text from the file
            contract_text = extract_text(tmp_file_path)
            
            if not contract_text.strip():
                raise HTTPException(status_code=400, detail="No text could be extracted from the file")
            
            # Analyze using Gemini Flash
            analysis = gemini_flash_complete(
                f"Analyze financial health and risks of this contract:\n{contract_text}",
                model_id="gemini-2.0-flash-exp"
            )
            
            return {"analysis": analysis}
            
        finally:
            # Clean up temporary file
            os.unlink(tmp_file_path)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing contract: {str(e)}")


@router.post("/analyze-text")
async def ai_analyze_text(text: str):
    """Analyze contract text using AI for financial health and risk assessment"""
    try:
        if not text.strip():
            raise HTTPException(status_code=400, detail="Text cannot be empty")
        
        # Analyze using Gemini Flash
        analysis = gemini_flash_complete(
            f"Analyze financial health and risks of this contract text:\n{text}",
            model_id="gemini-2.0-flash-exp"
        )
        
        return {"analysis": analysis}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing contract text: {str(e)}")
