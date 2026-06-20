import fitz  # PyMuPDF
from docx import Document
import os

def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except Exception as e:
        raise Exception(f"Failed to parse PDF: {str(e)}")
    return text

def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file."""
    text = ""
    try:
        doc = Document(file_path)
        for paragraph in doc.paragraphs:
            text += paragraph.text + "\n"
    except Exception as e:
        raise Exception(f"Failed to parse DOCX: {str(e)}")
    return text

def extract_resume_text(file_path: str) -> str:
    """Auto-detect file type and extract text."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    else:
        raise Exception("Unsupported file format. Please upload PDF or DOCX.")