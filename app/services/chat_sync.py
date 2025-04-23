import os
from datetime import datetime
from bson import ObjectId
from app.services.waha_api import fetch_chat_info_from_waha


def serialize_mongo_document(doc: dict):
    """
    Convierte todos los ObjectId de un documento Mongo en strings.
    """
    return {
        key: str(value) if isinstance(value, ObjectId) else value
        for key, value in doc.items()
    }


async def sync_latest_chats_from_overview(db, session_id: str, organization_id: str, limit: int = 20):
    """
    Sincroniza los últimos `limit` chats desde Waha overview con MongoDB.
    Crea o actualiza los chats en la colección `chats`.

    Retorna la lista de chats sincronizados para enviar al frontend.
    """
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    chat_overviews = await fetch_chat_info_from_waha(WAHA_API_URL, session_id, limit=limit)
    if not chat_overviews:
        print(f"[sync] No se pudo obtener overview para sesión {session_id}")
        return []

    synced_chats = []

    for chat in chat_overviews:
        contact_id = chat.get("id")
        if not contact_id:
            continue

        last_message = chat.get("lastMessage")
        last_msg = False
        if last_message:
            message_data_last = last_message.get("_data", {}).get("message", {})
            message_type = "text"
            for key in message_data_last.keys():
                if key.endswith("Message") and key != "extendedTextMessage":
                    message_type = key.replace("Message", "")
                    break

            last_msg = {
                "text": last_message.get("body") or "[media]",
                "timestamp": last_message.get("timestamp"),
                "type": message_type
            }

        # Datos base del chat
        base_data = {
            "organization_id": organization_id,
            "contact_id": contact_id,
            "provider": "web",
            "session": session_id,
            "status": "open",
            "name": chat.get("name"),
            "picture": chat.get("picture"),
            "is_archived": False,
            "is_silenced": False,
            "is_read": False,
            "tags": [],
            "last_message": last_msg,
            "updated_at": datetime.utcnow()
        }

        existing_chat = await db.chats.find_one({
            "organization_id": organization_id,
            "contact_id": contact_id,
            "session": session_id
        })

        if existing_chat:
            await db.chats.update_one(
                {"_id": existing_chat["_id"]},
                {"$set": base_data}
            )
            base_data["_id"] = existing_chat["_id"]
        else:
            base_data["created_at"] = datetime.utcnow()
            result = await db.chats.insert_one(base_data)
            base_data["_id"] = result.inserted_id

        synced_chats.append(serialize_mongo_document(base_data))

    return synced_chats
