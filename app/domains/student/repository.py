from sqlalchemy.orm import Session
from .models import Student, InteractionLog
from typing import List, Optional, Dict, Any

class StudentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_student(self, student_id: int) -> Optional[Student]:
        return self.db.query(Student).filter(Student.id == student_id).first()

    def get_by_email(self, email: str) -> Optional[Student]:
        return self.db.query(Student).filter(Student.email == email).first()

    def list_students(self, skip: int = 0, limit: int = 50) -> List[Student]:
        return self.db.query(Student).order_by(Student.id.desc()).offset(skip).limit(limit).all()

    def create_student(self, student_data: dict) -> Student:
        db_student = Student(**student_data)
        self.db.add(db_student)
        self.db.commit()
        self.db.refresh(db_student)
        return db_student

    def update_student(self, student_id: int, values: dict) -> Optional[Student]:
        student = self.get_student(student_id)
        if student is None:
            return None
        for field, value in values.items():
            setattr(student, field, value)
        self.db.commit()
        self.db.refresh(student)
        return student

    def delete_student(self, student_id: int) -> bool:
        student = self.get_student(student_id)
        if student is None:
            return False
        self.db.delete(student)
        self.db.commit()
        return True

    def add_interaction(self, student_id: int, interaction_data: dict) -> InteractionLog:
        db_interaction = InteractionLog(student_id=student_id, **interaction_data)
        self.db.add(db_interaction)
        self.db.commit()
        self.db.refresh(db_interaction)
        return db_interaction

    def update_ai_profile(self, student_id: int, profile: Dict[str, Any]) -> Student:
        student = self.get_student(student_id)
        if student:
            student.ai_inferred_profile = profile
            self.db.commit()
            self.db.refresh(student)
        return student
