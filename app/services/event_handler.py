import os
from datetime import datetime
from urllib.parse import urlparse
from app.routes.websockets import emit_event
from app.services.waha_api import fetch_chat_info_from_waha
from bson import ObjectId, timestamp


def replace_media_host(media):
    if media and "url" in media:
        parsed_url = urlparse(media["url"])
        new_host = os.getenv("WAHA_API_URL")
        if new_host:
            # Remover esquema, host y reconstruir la URL con el nuevo host
            media["url"] = f"{new_host}{parsed_url.path}"
    return media


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
    print(payload)
    if driver == "web" and event == "message":
        message_data = payload.get("payload", {})
        session_id = payload.get("session")
        contact_id = message_data.get("from") if not message_data.get("fromMe") else message_data.get("to")
        if contact_id == "status@broadcast":
            return
        WAHA_HOST = os.getenv("WAHA_API_URL")
        chat_infos = await fetch_chat_info_from_waha(WAHA_HOST, session_id, contact_id)
        chat_info = None
        for chat in chat_infos:
            if chat["id"] == contact_id:
                last_message = chat.get("lastMessage", {})
                message_data = last_message.get("_data", {}).get("message", {})
                message_type = "text"
                for key in message_data.keys():
                    if key.endswith("Message") and key != "extendedTextMessage":
                        message_type = key.replace("Message", "")
                        break

                chat_info = {
                    "name": chat.get("name"),
                    "picture": chat.get("picture"),
                    "last_message_type": message_type,
                }

        contact_name = chat_info["name"] if chat_info else payload.get("_data", {}).get("pushName", "")
        contact_picture = chat_info["picture"] if chat_info else None
        last_messages_type = chat_info["last_message_type"] if chat_info else "text"
        contact_doc = {
            "organization_id": organization_id,
            "contact_id": contact_id,
            "number": contact_id.split("@")[0],
            "name": contact_name,
            "picture": contact_picture,
            "status": "active",
            "tags": [],
            "is_archived": False,
            "is_silenced": False,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        contact = await db.contacts.find_one({
            "organizationId": organization_id,
            "contact_id": contact_id
        })

        webhook = await db.webhooks.find_one({"organizationId": organization_id})

        if webhook and webhook.get("active"):
            url = webhook["url"]
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            print(f"Webhook POST failed with status {response.status}")
            except Exception as e:
                print(f"Error sending POST request to webhook: {e}")
            
            
        if not contact:
            result = await db.contacts.insert_one(contact_doc)
            contact_id_db = result.inserted_id
        else:
            contact_id_db = contact["_id"]

        chat = await db.chats.find_one({
            "organization_id": organization_id,
            "contact_id": contact_id,
            "session": session_id
        })

        last_msg = {
            "text": message_data.get("body", "[media]"),
            "timestamp": message_data.get("timestamp"),
            "type": last_messages_type
        }

        if not chat:
            chat_doc = {
                "organization_id": organization_id,
                "contact_id": contact_id,
                "provider": driver,
                "session": session_id,
                "status": "open",
                "name": contact_name,
                "picture": contact_picture,
                "is_archived": False,
                "is_silenced": False,
                "is_read": False,
                "tags": [],
                "last_message": last_msg,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow()
            }
            result = await db.chats.insert_one(chat_doc)
            chat_id = result.inserted_id
        else:
            chat_id = chat["_id"]

        message_doc = {
            "id":contact_id,
            "sender": "agent",
            "content": message_data.get("body"),
            "status": "delivered",
            "timestamp":message_data.get("timestamp"),
            "attachments": get_attachments_from_message_data(message_data),
        }


        await db.chats.update_one(
            {"_id": chat_id},
            {"$set": {
                "last_message": last_msg,
                "updated_at": datetime.utcnow()
            }}
        )


        await emit_event(session_id, {
            "event": "new_message",
            "chatId": contact_id,
            "message": message_doc,
            "overview": chat_infos
        })




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
