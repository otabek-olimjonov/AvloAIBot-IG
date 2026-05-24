import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    __table_args__ = (
        CheckConstraint("source IN ('dm', 'comment')", name="ck_conversations_source"),
        CheckConstraint(
            "status IN ('active', 'ended', 'converted')", name="ck_conversations_status"
        ),
        CheckConstraint(
            "funnel_stage IN ('greeting', 'qualification', 'presentation', 'objection', 'closing', 'payment', 'completed')",
            name="ck_conversations_funnel_stage",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    instagram_user_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    instagram_username: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="active")
    funnel_stage: Mapped[str] = mapped_column(Text, nullable=False, default="greeting")
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ticket_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=True
    )
    started_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(nullable=True)

    messages: Mapped[list["Message"]] = relationship(
        "Message", back_populates="conversation", cascade="all, delete-orphan"
    )
