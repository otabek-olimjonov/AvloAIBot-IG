import uuid
from datetime import datetime
from pydantic import BaseModel


class ConversationResponse(BaseModel):
    id: uuid.UUID
    instagram_user_id: str
    instagram_username: str | None
    source: str
    status: str
    funnel_stage: str
    message_count: int
    ticket_id: uuid.UUID | None
    started_at: datetime
    ended_at: datetime | None

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    media_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedConversations(BaseModel):
    items: list[ConversationResponse]
    total: int
    page: int
    per_page: int


class PaginatedMessages(BaseModel):
    items: list[MessageResponse]
    total: int
