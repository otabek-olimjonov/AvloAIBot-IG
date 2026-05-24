import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Prompt
from app.schemas.prompt import PromptUpdate, PromptResponse
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/prompts", tags=["prompts"])


@router.get("", response_model=list[PromptResponse])
async def list_prompts(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Prompt))
    return result.scalars().all()


@router.put("/{prompt_id}", response_model=PromptResponse)
async def update_prompt(
    prompt_id: uuid.UUID,
    body: PromptUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Prompt).where(Prompt.id == prompt_id))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    prompt.content = body.content
    await db.commit()
    await db.refresh(prompt)
    return prompt
