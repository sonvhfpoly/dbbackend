from sqlalchemy.orm import Session
from .models import EducationPath, Recommendation
from typing import List, Optional

class GuidanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_all_paths(self) -> List[EducationPath]:
        return self.db.query(EducationPath).all()

    def create_path(self, path_data: dict) -> EducationPath:
        db_path = EducationPath(**path_data)
        self.db.add(db_path)
        self.db.commit()
        self.db.refresh(db_path)
        return db_path

    def create_recommendation(self, rec_data: dict) -> Recommendation:
        db_rec = Recommendation(**rec_data)
        self.db.add(db_rec)
        self.db.commit()
        self.db.refresh(db_rec)
        return db_rec

    def get_recommendations_by_student(self, student_id: int) -> List[Recommendation]:
        return self.db.query(Recommendation).filter(Recommendation.student_id == student_id).all()
