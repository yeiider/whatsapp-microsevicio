from fastapi import APIRouter, Request, Path, Header
from app.database import get_database
from app.services.event_handler import handle_event
from app.utils.auth import validate_organization

router = APIRouter()

@router.post("/webhook/{organization_id}")
async def receive_webhook(
    organization_id: str = Path(...),
    x_org_token: str = Header(...),
    request: Request = None
):
    db = get_database()
    await validate_organization(db, organization_id, x_org_token)
    body = await request.json()
    await handle_event(db, organization_id, body)
    return {"message": "received"}