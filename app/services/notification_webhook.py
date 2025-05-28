import aiohttp
from bson import ObjectId
from datetime import datetime
from app.utils.helpers import convert_datetime

def convert_to_serializable(data):
    if isinstance(data, dict):
        return {key: convert_to_serializable(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [convert_to_serializable(item) for item in data]
    elif isinstance(data, ObjectId):
        return str(data)
    elif isinstance(data, datetime):
        return data.isoformat()
    return data

async def send_notification_webhook(db, organization_id, message_data, chat, contact):
    webhooks = await db.webhooks.find({
        "organizationId": ObjectId(organization_id),
        "active": True,
    }).to_list(length=None)

    if not webhooks:
        print("🔕 No hay webhooks configurados.")
        return
    chat_copy = convert_to_serializable(chat)

    payload = {
        "message": {
            "id": message_data.get("id"),
            "from": message_data.get("from"),
            "to": message_data.get("to"),
            "fromMe": message_data.get("fromMe"),
            "timestamp": message_data.get("timestamp"),
            "body": message_data.get("body"),
            "media": message_data.get("media"),
        },
        "chat": chat_copy,
        "contact": contact,
        "organizationId": str(organization_id)
    }

    for webhook in webhooks:
        url = webhook.get("url")
        if not url:
            continue

        headers = {"Content-Type": "application/json"}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, headers=headers) as response:
                    status = response.status
                    response_data = await response.text()

                    # ✅ Guardar log
                    await db.webhooklogs.insert_one({
                        "webhookId": webhook["_id"],
                        "organizationId": ObjectId(organization_id),
                        "requestMethod": "POST",
                        "requestHeaders": headers,
                        "requestBody": payload,
                        "responseStatus": status,
                        "responseBody": response_data,
                        "timestamp": datetime.utcnow()
                    })

                    print(f"📤 Webhook enviado a {url}, status: {status}")
        except Exception as e:
            await db.webhooklogs.insert_one({
                "webhookId": webhook["_id"],
                "organizationId": ObjectId(organization_id),
                "requestMethod": "POST",
                "requestHeaders": headers,
                "requestBody": payload,
                "responseStatus": 500,
                "responseBody": str(e),
                "timestamp": datetime.utcnow()
            })
            print(f"❌ Error enviando webhook a {url}: {e}")
