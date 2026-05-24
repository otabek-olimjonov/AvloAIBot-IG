import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import FAQ
from app.schemas.faq import FAQCreate, FAQUpdate, FAQResponse
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/faq", tags=["faq"])


@router.get("", response_model=list[FAQResponse])
async def list_faq(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(FAQ).order_by(FAQ.sort_order))
    return result.scalars().all()


@router.post("", response_model=FAQResponse, status_code=status.HTTP_201_CREATED)
async def create_faq(
    body: FAQCreate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    faq = FAQ(**body.model_dump())
    db.add(faq)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.put("/{faq_id}", response_model=FAQResponse)
async def update_faq(
    faq_id: uuid.UUID,
    body: FAQUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(faq, field, value)
    await db.commit()
    await db.refresh(faq)
    return faq


@router.delete("/{faq_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_faq(
    faq_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(FAQ).where(FAQ.id == faq_id))
    faq = result.scalar_one_or_none()
    if not faq:
        raise HTTPException(status_code=404, detail="FAQ not found")
    await db.delete(faq)
    await db.commit()
