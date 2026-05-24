import uuid
from datetime import date
from pydantic import BaseModel


class PromotionBase(BaseModel):
    name: str
    type: str
    value: str
    description_for_bot: str | None = None
    promo_code: str | None = None
    start_date: date
    end_date: date
    product_ids: list[uuid.UUID] | None = None
    is_active: bool = True


class PromotionCreate(PromotionBase):
    pass


class PromotionUpdate(BaseModel):
    name: str | None = None
    type: str | None = None
    value: str | None = None
    description_for_bot: str | None = None
    promo_code: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    product_ids: list[uuid.UUID] | None = None
    is_active: bool | None = None


class PromotionResponse(PromotionBase):
    id: uuid.UUID

    model_config = {"from_attributes": True}
