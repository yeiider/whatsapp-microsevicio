from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from fastapi.encoders import jsonable_encoder
import os
import httpx
from datetime import datetime
from app.database import get_database
import json

router = APIRouter()

# Base URLs por proveedor
PROVIDER_URLS = {
    "web": os.getenv("WAHA_API_URL"),
    # futuros proveedores
    # "gupshup": os.getenv("GUPSHUP_API_URL"),
    # "twilio": os.getenv("TWILIO_API_URL"),
}

class SendMessageRequest(BaseModel):
    provider: str
    type: str
    session: str
    chatId: str
    user: str
    text: str = None
    caption: str = None
    url: str = None
    mimetype: str = None
    filename: str = None
    sessionId: str = None

# Función principal para construcción de payloads
def build_payload(provider: str, payload: SendMessageRequest) -> dict:
    if provider == "web":
        return build_waha_payload(payload)
    else:
        raise ValueError(f"Unsupported provider: {provider}")

# Limpia claves con valores None o booleanos no permitidos, excepto campos esperados
def clean_payload(data: dict) -> dict:
    allowed_bools = {"linkPreview", "linkPreviewHighQuality"}
    return {
        k: v for k, v in data.items()
        if v is not None and (not isinstance(v, bool) or k in allowed_bools)
    }

# Payloads específicos para WAHA
def build_waha_payload(payload: SendMessageRequest) -> dict:
    data = {
        "chatId": payload.chatId,
        "session": payload.session,
        "reply_to": None,
    }

    if payload.type == "text":
        data["text"] = payload.text
        data["linkPreview"] = True
        data["linkPreviewHighQuality"] = False
    elif payload.type == "image":
        data["file"] = {
            "mimetype": "image/jpeg",
            "filename": payload.filename or "image.jpg",
            "url": payload.url,
        }
        data["caption"] = payload.caption or ""
    elif payload.type == "file":
        data["file"] = {
            "mimetype": payload.mimetype,
            "filename": payload.filename,
            "url": payload.url,
        }
        data["caption"] = payload.caption or ""
    elif payload.type == "voice":
        data["file"] = {
            "mimetype": "audio/ogg; codecs=opus",
            "url": payload.url,
        }
    elif payload.type == "video":
        data["file"] = {
            "mimetype": "video/mp4",
            "filename": payload.filename,
            "url": payload.url,
        }
        data["caption"] = payload.caption or ""
        data["asNote"] = False
    else:
        raise ValueError("Invalid message type for WAHA")
    print(data)
    return data

@router.post("/api/send-message")
async def send_message(payload: SendMessageRequest):
    print(payload)
    base_url = PROVIDER_URLS.get(payload.provider)
    if not base_url:
        raise HTTPException(status_code=400, detail=f"Provider '{payload.provider}' not configured")

    endpoint_map = {
        "text": "/sendText",
        "image": "/sendImage",
        "file": "/sendFile",
        "voice": "/sendVoice",
        "video": "/sendVideo",
    }

    if payload.type not in endpoint_map:
        raise HTTPException(status_code=400, detail="Invalid message type")

    endpoint = f"{base_url}/api{endpoint_map[payload.type]}"
    print("Endpoint a usar:", endpoint)
    try:
        raw_data = build_payload(payload.provider, payload)
        cleaned = clean_payload(raw_data)
        data = jsonable_encoder(cleaned)
        print("Payload final a enviar:", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, json=data)

    if response.status_code not in [200, 201]:
        raise HTTPException(status_code=response.status_code, detail=response.text)

    # Intentar extraer el ID del mensaje desde la respuesta de Waha
    try:
        result = json.loads(response.text)
        message_id = result.get("key", {}).get("id")
    except Exception:
        message_id = None

    # Guardar mensaje en Mongo
    db = get_database()
    chat = await db.chats.find_one({"contact_id": payload.chatId})
    if not chat:
        # Si no existe, crear chat base con contact_id como el chatId para relacionarlo correctamente
        chat_doc = {
            "contact_id": payload.chatId,
            "provider": payload.provider,
            "status": "open",
            "is_archived": False,
            "is_silenced": False,
            "is_read": False,
            "tags": [],
            "last_message": {},
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
        chat_result = await db.chats.insert_one(chat_doc)
        chat_id = chat_result.inserted_id

    return result
