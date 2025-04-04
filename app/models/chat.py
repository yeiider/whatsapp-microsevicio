from pydantic import BaseModel
from datetime import datetime
from typing import Optional, List

class Chat(BaseModel):
    organization_id: str
    contact_id: str
    provider: str
    status: str = "open"
    name: str
    picture: str
    last_message_type:str = "text"
    is_archived: bool = False
    is_silenced: bool = False
    is_read: bool = False
    assigned_to: Optional[str]
    department: Optional[str]
    tags: List[str] = []
    last_message: Optional[dict]
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()