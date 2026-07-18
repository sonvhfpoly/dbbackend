from typing import List, Optional
from sqlalchemy.orm import Session
from .models import TBConversation, TBMessage, TBDocument, ConversationStatus, MessageRole

class TaskBuilderRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- Conversation ----

    def create_conversation(self, company_id: int, created_by: str) -> TBConversation:
        conversation = TBConversation(company_id=company_id, created_by=created_by)
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_conversation(self, conversation_id: int) -> Optional[TBConversation]:
        return self.db.query(TBConversation).filter(TBConversation.id == conversation_id).first()

    def update_conversation_status(self, conversation_id: int, status: ConversationStatus) -> Optional[TBConversation]:
        conversation = self.get_conversation(conversation_id)
        if conversation is None:
            return None
        conversation.status = status
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    # ---- Messages ----

    def add_message(
        self,
        conversation_id: int,
        role: MessageRole,
        content: str,
        open_questions: Optional[list] = None,
        proposed_versions: Optional[list] = None,
    ) -> TBMessage:
        message = TBMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            open_questions=open_questions,
            proposed_versions=proposed_versions,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, conversation_id: int) -> List[TBMessage]:
        return (
            self.db.query(TBMessage)
            .filter(TBMessage.conversation_id == conversation_id)
            .order_by(TBMessage.id)
            .all()
        )

    def get_latest_ai_message(self, conversation_id: int) -> Optional[TBMessage]:
        return (
            self.db.query(TBMessage)
            .filter(TBMessage.conversation_id == conversation_id, TBMessage.role == MessageRole.AI)
            .order_by(TBMessage.id.desc())
            .first()
        )

    # ---- Documents ----

    def create_document(
        self,
        conversation_id: int,
        filename: str,
        content_type: Optional[str],
        size_bytes: int,
        storage_url: str,
        extracted_text: Optional[str],
    ) -> TBDocument:
        document = TBDocument(
            conversation_id=conversation_id,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            storage_url=storage_url,
            extracted_text=extracted_text,
        )
        self.db.add(document)
        self.db.commit()
        self.db.refresh(document)
        return document

    def list_documents(self, conversation_id: int) -> List[TBDocument]:
        return self.db.query(TBDocument).filter(TBDocument.conversation_id == conversation_id).all()
