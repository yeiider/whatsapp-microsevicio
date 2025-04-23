from fastapi import APIRouter, Depends, HTTPException
from app.utils.auth import get_user_organization
from app.database import get_database
from app.services.chat_sync import sync_latest_chats_from_overview

router = APIRouter()


@router.post("/api/sync-chats/{session_id}/{user_id}")
async def sync_chats(session_id: str, user_id: str, db=Depends(get_database)):
    """
    Sincroniza todos los chats desde el overview de Waha y los guarda/actualiza en Mongo,
    usando el ID del usuario para obtener su organización.
    """
    try:
        organization_id = await get_user_organization(db, user_id)

        synced_chats = await sync_latest_chats_from_overview(
            db=db,
            session_id=session_id,
            organization_id=organization_id,
            limit=100  # o sin límite si quieres traer todo
        )

        return {
            "status": "success",
            "count": len(synced_chats),
            "chats": synced_chats
        }

    except Exception as e:

        import traceback
        error_info = {
            "error": str(e),
            "traceback": traceback.format_exc(),
            "line": traceback.extract_tb(e.__traceback__)[-1].lineno
        }
        raise HTTPException(status_code=500, detail=error_info)
