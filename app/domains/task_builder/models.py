from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, ForeignKey, Enum as SQLEnum, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from core.database import Base
import enum

class ConversationStatus(enum.Enum):
    COLLECTING = "COLLECTING"
    READY = "READY"
    TASK_CREATED = "TASK_CREATED"

class MessageRole(enum.Enum):
    ENTERPRISE = "enterprise"
    AI = "ai"

class TBConversation(Base):
    __tablename__ = "task_builder_conversations"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    # Not a FK: no user/auth model exists yet in this system (same convention
    # as Task.student_id) — plain caller-supplied identifier.
    created_by: Mapped[str] = mapped_column(String(255))
    status: Mapped[ConversationStatus] = mapped_column(SQLEnum(ConversationStatus), default=ConversationStatus.COLLECTING)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    company = relationship("Company")
    messages = relationship(
        "TBMessage", back_populates="conversation",
        cascade="all, delete-orphan", order_by="TBMessage.id",
    )
    documents = relationship("TBDocument", back_populates="conversation", cascade="all, delete-orphan")

class TBMessage(Base):
    __tablename__ = "task_builder_messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("task_builder_conversations.id"), index=True)
    role: Mapped[MessageRole] = mapped_column(SQLEnum(MessageRole))
    content: Mapped[str] = mapped_column(Text)
    # Only populated on role=ai messages: the AI's structured turn output, so
    # /open-questions can read the latest state straight from DB without
    # another AI call.
    open_questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    proposed_versions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    conversation = relationship("TBConversation", back_populates="messages")

class TBDocument(Base):
    __tablename__ = "task_builder_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("task_builder_conversations.id"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer)
    storage_url: Mapped[str] = mapped_column(String(1000))
    extracted_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    conversation = relationship("TBConversation", back_populates="documents")

    @property
    def extracted_text_length(self) -> int:
        """Read via TBDocumentRead (from_attributes) instead of returning the
        full extracted_text in every list/detail response."""
        return len(self.extracted_text) if self.extracted_text else 0
