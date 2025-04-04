from pydantic import BaseModel, Field
from typing import Optional, Dict
from datetime import datetime

class Message(BaseModel):
    chat_id: str  # Referencia al chat asociado
    message_id: str
    timestamp: int
    from_: str = Field(..., alias="from")
    to: str
    from_me: bool
    body: Optional[str]
    has_media: bool = False
    media: Optional[Dict] = None
    reply_to: Optional[Dict] = None
    session: Optional[str]
    user: Optional[Dict] = None
    me: Optional[Dict] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        allow_population_by_field_name = True