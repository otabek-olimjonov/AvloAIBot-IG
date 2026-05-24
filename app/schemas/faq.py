import uuid
from pydantic import BaseModel


class FAQBase(BaseModel):
    question: str
    answer: str
    sort_order: int = 0


class FAQCreate(FAQBase):
    pass


class FAQUpdate(BaseModel):
    question: str | None = None
    answer: str | None = None
    sort_order: int | None = None


class FAQResponse(FAQBase):
    id: uuid.UUID

    model_config = {"from_attributes": True}
