import os
from datetime import datetime
from urllib.parse import urlparse
from app.services.notification_webhook import send_notification_webhook

from app.services.chat_sync import sync_latest_chats_from_overview
from app.routes.websockets import emit_event
from bson import ObjectId


def replace_media_host(media):
    if media and "url" in media:
        parsed_url = urlparse(media["url"])
        new_host = os.getenv("WAHA_API_URL")
        if new_host:
            # Remover esquema, host y reconstruir la URL con el nuevo host
            media["url"] = f"{new_host}{parsed_url.path}"
    return media

def extract_chat_from_overview(chat_overviews, contact_id):
    for chat in chat_overviews:
        if chat.get("id") == contact_id:
            return chat
    return None


def convert_datetime(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime(i) for i in obj]
    return obj

def get_attachments_from_message_data(message_data):
    # Verifica si 'has_media' es True y si 'media' está presente en el mensaje
    if message_data.get('has_media') and 'media' in message_data:
        media = message_data['media']
        attachments = [
            {
                "id": message_data.get('id'),
                "type": get_media_type(media.get('mimetype', "")),
                "url": media.get('url'),
                "name": media.get('filename'),
                "mimetype": media.get('mimetype'),
                "width": media.get('width'),  # Si necesitas width
                "height": media.get('height'),  # Si necesitas height
                "size": media.get('size'),  # Si necesitas size
            }
        ]
        return attachments  # Devuelve la lista de attachments
    return None  # Devuelve None si no hay media


def get_media_type(mimetype):
    # Determina el tipo de media con base en el MIME type
    if mimetype.startswith("image"):
        return "image"
    elif mimetype.startswith("video"):
        return "video"
    elif mimetype.startswith("audio"):
        return "audio"
    elif mimetype.startswith("application"):
        return "document"
    else:
        return "unknown"




async def handle_event(db, organization_id, payload, driver,session_id):
    event = payload.get("event")
    print(event)
    from app.services.notification_webhook import send_notification_webhook

    if driver == "web" and event == "message":
        message_data = payload.get("payload", {})
        session_id = payload.get("session")
        contact_id = message_data.get("from") if not message_data.get("fromMe") else message_data.get("to")
        if contact_id == "status@broadcast":
            return

        # 1. Obtener contacto desde base


        # 2. Obtener chats (overview)
        chat_overviews = await sync_latest_chats_from_overview(db, session_id, organization_id)
        chat_data = next((c for c in chat_overviews if c.get("id") == contact_id), None)

        contact_data = await db.contacts.find_one({
            "contact_id": contact_id,
            "organizationId": ObjectId(organization_id)
        })
        # 3. Armar documento de mensaje
        message_doc = {
            "id": contact_id,
            "sender": "user",
            "content": message_data.get("body"),
            "status": "delivered",
            "timestamp": message_data.get("timestamp"),
            "attachments": get_attachments_from_message_data(message_data),
        }

        # 4. Emitir WebSocket
        await emit_event(session_id, {
            "event": "new_message",
            "chatId": contact_id,
            "message": message_doc,
            "overview": chat_overviews
        })

        # 5. Enviar webhook si hay
        await send_notification_webhook(db, organization_id, message_data, chat_data, contact_data)



    elif driver == "web" and event == "session.status":
        session_name = payload.get("payload", {}).get("name")
        new_status = payload.get("payload", {}).get("status")
        me = payload.get("me")
        if session_name:
            session_id= ObjectId(session_id)
            session = await db.whatsappsessions.find_one({"_id": session_id})
            if session:
                previous_status = session.get("status")
                updates = {
                    "status": new_status,
                    "lastActivity": datetime.utcnow(),
                    "updatedAt": datetime.utcnow()
                }
                if me:
                    updates["me"] = me

                await db.whatsappsessions.update_one(
                    {"_id": session["_id"]},
                    {"$set": updates}
                )

                if new_status == "WORKING":
                    print("Conectado")
                    await emit_event(organization_id, {
                        "event": "whatsapp:connected",
                        "organizationId": organization_id,
                        "sessionName": session_name
                    })
                else:
                    print("Desconectado")
                    print(organization_id)
                    await emit_event(organization_id, {
                        "event": "whatsapp:disconnected",
                        "organizationId": organization_id,
                        "sessionName": session_name
                    })
