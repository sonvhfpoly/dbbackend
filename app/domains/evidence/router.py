from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List, Optional
from core.database import get_db
from .schemas import EvidenceClaimCreate, EvidenceClaimRead, MentorDecisionRequest, EvidenceStatus
from .service import EvidenceService

router = APIRouter(prefix="/evidence", tags=["Evidence"])

@router.post(
    "/",
    response_model=EvidenceClaimRead,
    summary="Create an evidence claim (AI draft) for a student's skill on a task",
)
def create_claim(payload: EvidenceClaimCreate, db: Session = Depends(get_db)):
    return EvidenceService(db).create_claim(payload)

@router.get(
    "/pending-mentor",
    response_model=List[EvidenceClaimRead],
    summary="List claims awaiting a mentor decision",
)
def list_pending_mentor(db: Session = Depends(get_db)):
    return EvidenceService(db).list_pending_mentor()

@router.get("/{claim_id}", response_model=EvidenceClaimRead, summary="Get an evidence claim's detail")
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    return EvidenceService(db).get_claim(claim_id)

@router.post(
    "/{claim_id}/student-review",
    response_model=EvidenceClaimRead,
    summary="Student acknowledges the AI-drafted claim",
)
def student_review(claim_id: int, db: Session = Depends(get_db)):
    return EvidenceService(db).student_review(claim_id)

@router.post(
    "/{claim_id}/submit-to-mentor",
    response_model=EvidenceClaimRead,
    summary="Send a student-reviewed claim to the mentor queue",
)
def submit_to_mentor(claim_id: int, db: Session = Depends(get_db)):
    return EvidenceService(db).submit_to_mentor(claim_id)

@router.post(
    "/{claim_id}/mentor-decision",
    response_model=EvidenceClaimRead,
    summary="Mentor verifies, rejects, or requests more evidence for a claim",
    description="VERIFIED is the only decision that updates the student's skill profile — "
                "the human-in-the-loop point required before any skill level changes.",
)
def mentor_decision(claim_id: int, request: MentorDecisionRequest, db: Session = Depends(get_db)):
    return EvidenceService(db).mentor_decide(claim_id, request.mentor_id, request.decision, request.comment)

@router.get(
    "/students/{student_id}",
    response_model=List[EvidenceClaimRead],
    summary="List a student's evidence claims, optionally filtered by status",
)
def list_by_student(student_id: int, status: Optional[EvidenceStatus] = None, db: Session = Depends(get_db)):
    return EvidenceService(db).list_by_student(student_id, status=status.value if status else None)
