import mimetypes
import uuid
from io import BytesIO
from typing import Optional

from docx import Document as DocxDocument
from fastapi import HTTPException, status
from google.cloud import storage
from pypdf import PdfReader

from core.config import settings


def extract_text(filename: str, content_type: Optional[str], content: bytes) -> Optional[str]:
    """Best-effort text extraction for the file types this feature actually
    expects (PDF/DOCX/plain text). Returns None (rather than raising) on
    unrecognized types or a corrupt file — the document is still stored, just
    without extracted_text for the AI to read."""
    guessed_type = content_type or mimetypes.guess_type(filename)[0] or ""
    lower_name = filename.lower()
    try:
        if "pdf" in guessed_type or lower_name.endswith(".pdf"):
            reader = PdfReader(BytesIO(content))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if "wordprocessingml" in guessed_type or lower_name.endswith(".docx"):
            doc = DocxDocument(BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs)
        if guessed_type.startswith("text/") or lower_name.endswith(".txt"):
            return content.decode("utf-8", errors="ignore")
        return None
    except Exception:
        return None


def upload_document(conversation_id: int, filename: str, content_type: Optional[str], content: bytes) -> str:
    """Uploads to GCS using the same ADC/service account as Vertex AI — no
    separate credentials to manage on Cloud Run."""
    if not settings.TASK_BUILDER_GCS_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document upload is not configured: TASK_BUILDER_GCS_BUCKET is missing",
        )

    client = storage.Client(project=settings.VERTEX_PROJECT_ID) if settings.VERTEX_PROJECT_ID else storage.Client()
    bucket = client.bucket(settings.TASK_BUILDER_GCS_BUCKET)
    # uuid-prefixed so re-uploading the same filename to the same conversation
    # doesn't silently overwrite an earlier blob.
    blob_name = f"task-builder/{conversation_id}/{uuid.uuid4().hex}_{filename}"
    blob = bucket.blob(blob_name)

    try:
        blob.upload_from_string(content, content_type=content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Document upload to GCS failed: {exc}",
        ) from exc

    return f"gs://{settings.TASK_BUILDER_GCS_BUCKET}/{blob_name}"
