import base64
import os
import fitz  # PyMuPDF
from pathlib import Path

DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)


def pdf_to_text(file_path: str) -> str:
    doc = fitz.open(file_path)
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()
    return text[:10000]


def image_to_base64(file_path: str) -> str:
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def get_file_text(file_path: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        return {"status": "error", "error": "File not found"}

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = pdf_to_text(file_path)
        return {"status": "ok", "type": "pdf", "text": text}
    elif suffix in (".jpg", ".jpeg", ".png", ".webp"):
        b64 = image_to_base64(file_path)
        return {"status": "ok", "type": "image", "base64": b64, "mime": f"image/{suffix.lstrip('.')}"}
    else:
        return {"status": "error", "error": f"Unsupported file type: {suffix}"}
