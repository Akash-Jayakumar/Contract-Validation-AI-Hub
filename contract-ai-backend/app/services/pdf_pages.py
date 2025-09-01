from pdfminer.high_level import extract_text_to_fp
from pdfminer.layout import LAParams
from io import StringIO

def extract_pages_text(file_path: str) -> list[tuple[int, str]]:
    """
    Returns [(page_no (1-based), page_text), ...]
    """
    from pdfminer.pdfpage import PDFPage
    pages_out: list[tuple[int, str]] = []
    laparams = LAParams()
    with open(file_path, "rb") as fp:
        for pno, page in enumerate(PDFPage.get_pages(fp), start=1):
            # render a single page to text
            f = StringIO()
            extract_text_to_fp(open(file_path, "rb"), f, laparams=laparams, page_numbers=[pno-1])
            pages_out.append((pno, f.getvalue()))
    return pages_out
