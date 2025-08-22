import os
from PIL import Image
import pytesseract
from pdf2image import convert_from_path

# Configure tesseract path - try to find it automatically or use environment variable
def get_tesseract_path():
    """Get tesseract executable path from environment or common locations"""
    # Check environment variable first
    tesseract_path = os.getenv('TESSERACT_PATH')
    if tesseract_path and os.path.exists(tesseract_path):
        return tesseract_path
    
    # Common Windows path
    windows_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(windows_path):
        return windows_path
    
    # Common Linux path
    linux_path = "/usr/bin/tesseract"
    if os.path.exists(linux_path):
        return linux_path
    
    # Try to find in PATH
    try:
        import shutil
        return shutil.which("tesseract")
    except:
        pass
    
    raise FileNotFoundError(
        "Tesseract not found. Please install Tesseract OCR and set TESSERACT_PATH environment variable "
        "or ensure tesseract is in your system PATH."
    )

# Set tesseract path
pytesseract.pytesseract.tesseract_cmd = get_tesseract_path()

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

def extract_text_from_pdf(file_path: str, lang: str = "eng") -> str:
    """
    Extract text specifically from PDF files
    
    Args:
        file_path: Path to the PDF file
        lang: Language code for OCR (default: eng)
    
    Returns:
        Extracted text as string
    """
    return extract_text(file_path, lang)

def extract_text_from_image(file_path: str, lang: str = "eng") -> str:
    """
    Extract text specifically from image files
    
    Args:
        file_path: Path to the image file
        lang: Language code for OCR (default: eng)
    
    Returns:
        Extracted text as string
    """
    return extract_text(file_path, lang)
