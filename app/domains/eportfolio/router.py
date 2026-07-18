from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from .schemas import EPortfolioRead, EPortfolioBusinessView, ShareSettingRead, ShareSettingUpdate
from .service import EPortfolioService

router = APIRouter(prefix="/eportfolio", tags=["ePortfolio"])

@router.get(
    "/students/{student_id}",
    response_model=EPortfolioRead,
    summary="A student's own full ePortfolio (verified skills, evidence, tasks, career suggestions)",
)
def get_student_portfolio(student_id: int, db: Session = Depends(get_db)):
    return EPortfolioService(db).get_student_view(student_id)

@router.get(
    "/students/{student_id}/business-view",
    response_model=EPortfolioBusinessView,
    summary="The filtered, professional view a consenting business is allowed to see",
    description="403s if the student hasn't opted into share_with_business via the share-settings endpoint below.",
)
def get_business_portfolio(student_id: int, db: Session = Depends(get_db)):
    return EPortfolioService(db).get_business_view(student_id)

@router.put(
    "/students/{student_id}/share-settings",
    response_model=ShareSettingRead,
    summary="Student sets whether businesses may view their ePortfolio",
)
def update_share_setting(student_id: int, payload: ShareSettingUpdate, db: Session = Depends(get_db)):
    return EPortfolioService(db).update_share_setting(student_id, payload.share_with_business)
