import uuid
from datetime import datetime
from pydantic import BaseModel


class SettingResponse(BaseModel):
    id: uuid.UUID
    key: str
    value: str
    updated_at: datetime

    model_config = {"from_attributes": True}


class SettingsBatchUpdate(BaseModel):
    settings: dict[str, str]


class SettingUpdate(BaseModel):
    value: str
