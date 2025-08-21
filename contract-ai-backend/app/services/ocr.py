import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# 👇 Explicitly tell pytesseract where tesseract.exe is located
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

def extract_text(file_path: str, lang: str = "eng") -> str:
    """
    Extract text from image or PDF files using OCR
    
    Args:
        file_path: Path to the file
        lang: Language code for OCR (default: eng)
    
    Returns:
        Extracted text as string
    """
    ext = os.path.splitext(file_path)[-1].lower()
    text = ""
    
    if ext in [".jpg", ".jpeg", ".png", ".tiff", ".bmp"]:
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img, lang=lang)
    elif ext == ".pdf":
        pages = convert_from_path(file_path, dpi=300)
        for page_img in pages:
            page_text = pytesseract.image_to_string(page_img, lang=lang)
            text += page_text + "\n"
    else:
        raise ValueError(f"Unsupported file type: {ext}")
    
    return text.strip()
