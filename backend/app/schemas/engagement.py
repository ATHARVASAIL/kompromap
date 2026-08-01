import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class EngagementCreate(BaseModel):
    name: str
    client_name: str | None = None
    activate: bool = True  # switch to it immediately, the common case


class EngagementUpdate(BaseModel):
    name: str | None = None
    client_name: str | None = None


class EngagementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    client_name: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime
