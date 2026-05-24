import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Conversation, Message
from app.schemas.conversation import (
    ConversationResponse,
    MessageResponse,
    PaginatedConversations,
    PaginatedMessages,
)
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=PaginatedConversations)
async def list_conversations(
    status: str | None = Query(default=None),
    funnel_stage: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    query = select(Conversation)
    if status:
        query = query.where(Conversation.status == status)
    if funnel_stage:
        query = query.where(Conversation.funnel_stage == funnel_stage)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar_one()

    query = query.order_by(Conversation.started_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)

    return PaginatedConversations(
        items=result.scalars().all(),
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


@router.get("/{conversation_id}/messages", response_model=PaginatedMessages)
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(get_current_user),
):
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conversation_id)
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return PaginatedMessages(items=messages, total=len(messages))
