import os
from datetime import datetime, timedelta
from bson import ObjectId

from app.services.waha_api import fetch_chat_info_from_waha
from app.services.contact_extended import sync_contact_extended


def serialize_mongo_document(doc: dict):
    """Convierte los ObjectId en strings para que sean JSON-friendly."""
    return {
        key: str(value) if isinstance(value, ObjectId) else value
        for key, value in doc.items()
    }


async def sync_latest_chats_from_overview(
    db,
    session_id: str,
    organization_id: str,
    limit: int = 20,
):
    """
    Sincroniza la lista de chats/overviews que devuelve Waha y los guarda
    (o actualiza) en la colección `chats`.
    """
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    chat_overviews = await fetch_chat_info_from_waha(
        WAHA_API_URL,
        session_id,
        limit=limit,
    )
    if not chat_overviews:
        print(f"[sync] No se pudo obtener overview para sesión {session_id}")
        return []

    mongodb_operations = []
    # En caso de que un chat no traiga timestamp, usamos el último válido
    prev_valid_timestamp = int(datetime.utcnow().timestamp())

    for idx, chat in enumerate(chat_overviews):
        contact_id = chat.get("id")
        if not contact_id:
            continue

        is_group = contact_id.endswith("@g.us")

        # ------------------------------------------------------------------
        # LAST MESSAGE
        # ------------------------------------------------------------------
        last_message = chat.get("lastMessage")
        last_msg = False
        raw_timestamp = None

        if last_message:
            # El type está dentro de `_data.message` o directo en `_data`
            message_data_last = (
                last_message.get("_data", {}).get("message", {})
                or last_message.get("_data", {})
            )
            message_type = message_data_last.get("type")

            raw_timestamp = last_message.get("timestamp")
            last_msg = {
                "text": last_message.get("body") or "[media]",
                "timestamp": raw_timestamp,
                "type": message_type,
            }

        # Garantiza que siempre tengamos un timestamp coherente
        if raw_timestamp:
            prev_valid_timestamp = raw_timestamp
        else:
            raw_timestamp = prev_valid_timestamp + idx

        updated_at = datetime.utcfromtimestamp(raw_timestamp) + timedelta(
            milliseconds=idx
        )

        # ------------------------------------------------------------------
        # METADATOS NUEVOS DEL BLOQUE _chat
        # ------------------------------------------------------------------
        chat_meta = chat.get("_chat", {})

        unread_count = chat_meta.get("unreadCount", 0)
        is_archived_flag = chat_meta.get("archived", False)
        is_pinned = chat_meta.get("pinned", False)
        is_muted = chat_meta.get("isMuted", False)
        mute_expires_ts = chat_meta.get("muteExpiration") or None

        device_type = (
            chat_meta.get("lastMessage", {}).get("deviceType")
            if chat_meta.get("lastMessage")
            else None
        )

        # ------------------------------------------------------------------
        # BASE DATA (para insert o update)
        # ------------------------------------------------------------------
        base_data = {
            "organization_id": organization_id,
            "contact_id": contact_id,
            "provider": "web",
            "session": session_id,
            "status": "open",
            "name": chat.get("name"),
            "picture": chat.get("picture"),
            "is_archived": is_archived_flag,
            "is_pinned": is_pinned,
            "is_muted": is_muted,
            "mute_expires_at": (
                datetime.utcfromtimestamp(mute_expires_ts)
                if mute_expires_ts
                else None
            ),
            "unread_count": unread_count,
            "is_read": unread_count == 0,
            "tags": [],
            "message_status": (
                last_message.get("ackName") if last_message else None
            ),
            "is_group": is_group,
            "device_type": device_type,
            "last_message": last_msg,
            "last_activity": raw_timestamp,
            "updated_at": updated_at,
        }

        # ------------------------------------------------------------------
        # UPSERT
        # ------------------------------------------------------------------
        existing_chat = await db.chats.find_one(
            {
                "organization_id": organization_id,
                "contact_id": contact_id,
                "session": session_id,
            }
        )

        if existing_chat:
            # ---------- UPDATE ----------
            await db.chats.update_one(
                {"_id": existing_chat["_id"]},
                {
                    "$set": {
                        "name": chat.get("name"),
                        "picture": chat.get("picture"),
                        "last_message": last_msg,
                        "updated_at": updated_at,
                        "message_status": (
                            last_message.get("ackName") if last_message else None
                        ),
                        "last_activity": raw_timestamp,
                        "unread_count": unread_count,
                        "is_archived": is_archived_flag,
                        "is_pinned": is_pinned,
                        "is_muted": is_muted,
                        "mute_expires_at": (
                            datetime.utcfromtimestamp(mute_expires_ts)
                            if mute_expires_ts
                            else None
                        ),
                        "device_type": device_type,
                        "is_read": unread_count == 0,
                    },
                    "$currentDate": {"lastUpdated": True},
                },
            )
            updated_chat = await db.chats.find_one({"_id": existing_chat["_id"]})
            mongodb_operations.append(serialize_mongo_document(updated_chat))

        else:
            # ---------- INSERT ----------
            base_data["created_at"] = updated_at
            result = await db.chats.insert_one(base_data)
            base_data["_id"] = result.inserted_id
            mongodb_operations.append(serialize_mongo_document(base_data))

            # Alta / sync de contacto extendido (solo para chats 1:1)
            if not is_group:
                await sync_contact_extended(
                    db=db,
                    contact_id=contact_id,
                    name=chat.get("name"),
                    phone=contact_id.replace("@c.us", ""),
                    picture=chat.get("picture"),
                    organization_id=organization_id,
                    updated_at=updated_at,
                )

    return mongodb_operations
