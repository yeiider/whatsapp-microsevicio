from fastapi import APIRouter, Request, Path, Response
from app.services.waha_api import create_session_in_waha, get_qr_code_from_waha, delete_session_if_exists

router = APIRouter()

@router.post("/api/whatsapp/sessions")
async def create_whatsapp_session(request: Request):
    data = await request.json()

    organization_id = data.get("organizationId")
    phone_number = data.get("phoneNumber")
    driver = data.get("driver")
    session_name = data.get("sessionName")

    if not all([organization_id, phone_number, driver, session_name]):
        return {"error": "Missing required fields"}

    await create_session_in_waha(session_name, organization_id, driver)

    return {"message": "Session created in Waha", "sessionName": session_name}

@router.delete("/api/whatsapp/sessions/{session_name}")
async def delete_whatsapp_session(session_name: str = Path(...)):
    try:
        await delete_session_if_exists(session_name)
        return {"message": f"Session '{session_name}' deleted from Waha if it existed"}
    except Exception as e:
        return {"error": str(e)}



@router.get("/api/whatsapp/qr/{session_name}")
async def get_whatsapp_qr(session_name: str = Path(...)):
    try:
        qr_base64 = await get_qr_code_from_waha(session_name)
        return Response(content=qr_base64, media_type="image/png")

    except Exception as e:
        return {"error": str(e)}
