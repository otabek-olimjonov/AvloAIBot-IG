import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Promotion
from app.schemas.promotion import PromotionCreate, PromotionUpdate, PromotionResponse
from app.services.auth import get_current_user, require_admin, UserInfo

router = APIRouter(prefix="/promotions", tags=["promotions"])


@router.get("", response_model=list[PromotionResponse])
async def list_promotions(
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Promotion))
    return result.scalars().all()


@router.post("", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
async def create_promotion(
    body: PromotionCreate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    promo = Promotion(**body.model_dump())
    db.add(promo)
    await db.commit()
    await db.refresh(promo)
    return promo


@router.put("/{promo_id}", response_model=PromotionResponse)
async def update_promotion(
    promo_id: uuid.UUID,
    body: PromotionUpdate,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(promo, field, value)
    await db.commit()
    await db.refresh(promo)
    return promo


@router.delete("/{promo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_promotion(
    promo_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _: UserInfo = Depends(require_admin),
):
    result = await db.execute(select(Promotion).where(Promotion.id == promo_id))
    promo = result.scalar_one_or_none()
    if not promo:
        raise HTTPException(status_code=404, detail="Promotion not found")
    await db.delete(promo)
    await db.commit()
