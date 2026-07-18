from typing import List, Optional
from sqlalchemy.orm import Session
from .models import EvidenceClaim, EvidenceStatus

class EvidenceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_claim(self, data: dict) -> EvidenceClaim:
        claim = EvidenceClaim(**data)
        self.db.add(claim)
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def get_claim(self, claim_id: int) -> Optional[EvidenceClaim]:
        return self.db.query(EvidenceClaim).filter(EvidenceClaim.id == claim_id).first()

    def update_claim(self, claim_id: int, **fields) -> Optional[EvidenceClaim]:
        claim = self.get_claim(claim_id)
        if claim is None:
            return None
        for key, value in fields.items():
            setattr(claim, key, value)
        self.db.commit()
        self.db.refresh(claim)
        return claim

    def list_by_student(self, student_id: int, status: Optional[str] = None) -> List[EvidenceClaim]:
        query = self.db.query(EvidenceClaim).filter(EvidenceClaim.student_id == student_id)
        if status:
            query = query.filter(EvidenceClaim.status == status)
        return query.order_by(EvidenceClaim.created_at.desc()).all()

    def list_pending_mentor(self) -> List[EvidenceClaim]:
        return (
            self.db.query(EvidenceClaim)
            .filter(EvidenceClaim.status == EvidenceStatus.PENDING_MENTOR)
            .order_by(EvidenceClaim.created_at.asc())
            .all()
        )
