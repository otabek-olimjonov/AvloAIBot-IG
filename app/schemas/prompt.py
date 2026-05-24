import uuid
from datetime import datetime
from pydantic import BaseModel


class PromptUpdate(BaseModel):
    content: str


class PromptResponse(BaseModel):
    id: uuid.UUID
    type: str
    content: str
    updated_at: datetime

    model_config = {"from_attributes": True}
