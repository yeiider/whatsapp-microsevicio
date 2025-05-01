from fastapi import APIRouter, Request, Path, Header, HTTPException
from app.database import get_database
from app.services.event_handler import handle_event
from app.utils.auth import validate_organization
from bson import ObjectId

router = APIRouter()


@router.post("/webhook/{session_name}")
async def receive_webhook(
        session_name: str = Path(...),
        x_org_token: str = Header(...),
        driver: str = Header(...),
        request: Request = None
):
    db = get_database()
    body = await request.json()
    # Buscar la sesión en Mongo usando el ID (que también es el session_name)
    try:
        session_id = ObjectId(session_name)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid session ID format")

    session = await db.whatsappsessions.find_one({"_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    organization = await db.organizations.find_one({"_id": ObjectId(session["organizationId"])})
    if not organization:
        raise HTTPException(status_code=404, detail="Organization not found")

    organization_uuid = organization.get("uuid")
    # Eliminar los últimos 8 caracteres de x_org_token
    x_org_token = x_org_token[:-9]
    # Validar que el session pertenezca a la organización indicada
    if organization_uuid != x_org_token:
        raise HTTPException(status_code=403, detail="Invalid organization for this session")

    # Validar que el token corresponda a la organización
    await validate_organization(db, organization.get("_id"), x_org_token)

    if session.get("provider") != driver:
        raise HTTPException(status_code=403, detail="Driver mismatch")

    # Procesar evento

    await handle_event(db, session["organizationId"], body, driver, session_name)

    return {"message": "received"}
