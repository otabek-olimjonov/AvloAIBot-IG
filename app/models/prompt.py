import uuid
from datetime import datetime
from sqlalchemy import Text, CheckConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base


class Prompt(Base):
    __tablename__ = "prompts"

    __table_args__ = (
        CheckConstraint(
            "type IN ('system', 'greeting', 'qualification', 'presentation', 'objections', 'closing', 'upsell')",
            name="ck_prompts_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    type: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False, server_default=func.now(), onupdate=func.now()
    )
