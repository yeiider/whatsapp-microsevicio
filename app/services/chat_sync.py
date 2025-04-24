import os
from datetime import datetime, timedelta
from bson import ObjectId
from app.services.waha_api import fetch_chat_info_from_waha
from app.services.contact_extended import sync_contact_extended


def serialize_mongo_document(doc: dict):
    return {
        key: str(value) if isinstance(value, ObjectId) else value
        for key, value in doc.items()
    }


async def sync_latest_chats_from_overview(db, session_id: str, organization_id: str, limit: int = 20):
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    chat_overviews = await fetch_chat_info_from_waha(WAHA_API_URL, session_id, limit=limit)
    if not chat_overviews:
        print(f"[sync] No se pudo obtener overview para sesión {session_id}")
        return []

    synced_chats = []
    prev_valid_timestamp = int(datetime.utcnow().timestamp())

    for idx, chat in enumerate(chat_overviews):
        contact_id = chat.get("id")
        if not contact_id:
            continue

        is_group = contact_id.endswith("@g.us")
        last_message = chat.get("lastMessage")
        last_msg = False
        raw_timestamp = None

        if last_message:
            message_data_last = last_message.get("_data", {}).get("message", {})
            message_type = "text"
            for key in message_data_last.keys():
                if key.endswith("Message") and key != "extendedTextMessage":
                    message_type = key.replace("Message", "")
                    break

            raw_timestamp = last_message.get("timestamp")
            last_msg = {
                "text": last_message.get("body") or "[media]",
                "timestamp": raw_timestamp,
                "type": message_type
            }

        # Si no hay timestamp, usamos el anterior válido y lo incrementamos
        if raw_timestamp:
            prev_valid_timestamp = raw_timestamp
        else:
            raw_timestamp = prev_valid_timestamp + idx

        updated_at = datetime.utcfromtimestamp(raw_timestamp) + timedelta(milliseconds=idx)

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
            "is_group": is_group,
            "last_message": last_msg,
            "last_activity": raw_timestamp,
            "updated_at": updated_at
        }

        existing_chat = await db.chats.find_one({
            "organization_id": organization_id,
            "contact_id": contact_id,
            "session": session_id
        })

        if existing_chat:
            await db.chats.update_one(
                {"_id": existing_chat["_id"]},
                {
                    "$set": {
                        "name": chat.get("name"),
                        "picture": chat.get("picture"),
                        "last_message": last_msg,
                        "updated_at": updated_at,
                        "last_activity": raw_timestamp
                    }
                }
            )
            base_data["_id"] = existing_chat["_id"]
        else:
            base_data["created_at"] = updated_at
            result = await db.chats.insert_one(base_data)
            base_data["_id"] = result.inserted_id

            if not is_group:
                await sync_contact_extended(
                    db=db,
                    contact_id=contact_id,
                    name=chat.get("name"),
                    phone=contact_id.replace("@c.us", ""),
                    picture=chat.get("picture"),
                    organization_id=organization_id,
                    updated_at=updated_at
                )

        synced_chats.append(serialize_mongo_document(base_data))

    return synced_chats
