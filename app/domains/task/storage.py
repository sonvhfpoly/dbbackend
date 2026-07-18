import uuid
from typing import Optional

from fastapi import HTTPException, status
from google.cloud import storage

from core.config import settings


def upload_submission_file(submission_id: int, filename: str, content_type: Optional[str], content: bytes) -> str:
    """Uploads to GCS using the same ADC/service account as Vertex AI — no
    separate credentials to manage on Cloud Run. Returns a public HTTPS URL:
    SUBMISSION_FILES_GCS_BUCKET has allUsers:objectViewer granted at the
    bucket-IAM level (a deliberate org-policy exception for this bucket only
    — see core/config.py), so the object is viewable at this URL as soon as
    the upload completes, no auth required."""
    if not settings.SUBMISSION_FILES_GCS_BUCKET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Submission file upload is not configured: SUBMISSION_FILES_GCS_BUCKET is missing",
        )

    client = storage.Client(project=settings.VERTEX_PROJECT_ID) if settings.VERTEX_PROJECT_ID else storage.Client()
    bucket = client.bucket(settings.SUBMISSION_FILES_GCS_BUCKET)
    # uuid-prefixed so re-uploading the same filename to the same submission
    # doesn't silently overwrite an earlier blob.
    blob_name = f"submissions/{submission_id}/{uuid.uuid4().hex}_{filename}"
    blob = bucket.blob(blob_name)

    try:
        blob.upload_from_string(content, content_type=content_type or "application/octet-stream")
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Submission file upload to GCS failed: {exc}",
        ) from exc

    # Not blob.make_public(): object-level ACLs are rejected outright under
    # uniform-bucket-level-access. Public read comes entirely from the
    # bucket's own IAM policy (allUsers:objectViewer) — this URL is the
    # standard public-object address.
    return f"https://storage.googleapis.com/{settings.SUBMISSION_FILES_GCS_BUCKET}/{blob_name}"
