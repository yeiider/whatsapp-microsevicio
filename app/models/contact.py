from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class Contact(BaseModel):
    organization_id: str
    contact_id: str
    number: str
    name: Optional[str]
    picture: Optional[str]
    status: str = "active"
    is_archived: bool = False
    is_silenced: bool = False
    assigned_to: Optional[str]
    department: Optional[str]
    tags: List[str] = []
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()