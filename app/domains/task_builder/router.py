from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session
from core.database import get_db
from .schemas import (
    TBConversationCreate, TBMessageCreate, TaskBuilderTurn,
    OpenQuestionsRead, TBConversationRead, TBDocumentRead,
    GenerateTaskRequest, GenerateTaskResult,
)
from .service import TaskBuilderService

router = APIRouter(prefix="/task-builder", tags=["AI Task Builder"])

@router.post(
    "/conversations",
    response_model=TaskBuilderTurn,
    summary="Start a new AI task-builder conversation with the enterprise's opening request",
)
def start_conversation(request: TBConversationCreate, db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    return service.start_conversation(request.company_id, request.created_by, request.message)

@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=TaskBuilderTurn,
    summary="Send the next enterprise message in an existing conversation",
)
def add_message(conversation_id: int, request: TBMessageCreate, db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    return service.add_message(conversation_id, request.message, confirm=request.confirm)

@router.post(
    "/conversations/{conversation_id}/documents",
    response_model=TBDocumentRead,
    summary="Upload a reference document (PDF/DOCX/plain text) for the AI to read",
    description="Stores the file in GCS and extracts its text so subsequent turns in this "
                "conversation can reference its content.",
)
async def upload_document(conversation_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    content = await file.read()
    return service.add_document(conversation_id, file.filename, file.content_type, content)

@router.get(
    "/conversations/{conversation_id}/open-questions",
    response_model=OpenQuestionsRead,
    summary="Get the list of questions the AI still needs confirmed before it can propose task versions",
    description="Read-only — reflects the latest AI turn already stored in the DB, no new AI call.",
)
def get_open_questions(conversation_id: int, db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    return service.get_open_questions(conversation_id)

@router.get(
    "/conversations/{conversation_id}",
    response_model=TBConversationRead,
    summary="Get the full conversation history, including attached documents",
)
def get_conversation(conversation_id: int, db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    return service.get_conversation(conversation_id)

@router.post(
    "/conversations/{conversation_id}/generate-task",
    response_model=GenerateTaskResult,
    summary="Create the real Task from a proposed version once the enterprise confirms it",
    description="Requires the conversation's latest AI turn to have status=READY. Creates exactly "
                "one Task matching the selected_version, with requires_mentor_approval=True as usual "
                "— mentor review happens through the existing task/submission approval flow.",
)
def generate_task(conversation_id: int, request: GenerateTaskRequest, db: Session = Depends(get_db)):
    service = TaskBuilderService(db)
    return service.generate_task(conversation_id, request.selected_version)
