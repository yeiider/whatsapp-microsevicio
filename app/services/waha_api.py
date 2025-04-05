import os
import aiohttp

async def fetch_chat_info_from_waha(host: str, session_name: str, contact_id: str):
    url = f"{host}/api/{session_name}/chats/overview?page=1&limit=20"
    print(url)
    async with aiohttp.ClientSession() as session:

        async with session.get(url) as response:
            if response.status != 200:
                return None


            chats = await response.json()
            for chat in chats:
                if chat["id"] == contact_id:
                    last_message = chat.get("lastMessage", {})
                    message_data = last_message.get("_data", {}).get("message", {})
                    message_type = "text"
                    for key in message_data.keys():
                        if key.endswith("Message") and key != "extendedTextMessage":
                            message_type = key.replace("Message", "")
                            break

                    return {
                        "name": chat.get("name"),
                        "picture": chat.get("picture"),
                        "last_message_type": message_type
                    }
    return None


async def delete_session_if_exists(session_name: str):
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    async with aiohttp.ClientSession() as session:
        check_url = f"{WAHA_API_URL}/api/sessions/{session_name}"
        async with session.get(check_url) as check_response:
            if check_response.status != 404:
                async with session.delete(check_url) as delete_response:
                    delete_response.raise_for_status()

async def create_session_in_waha(session_name: str, organization_id: str, driver: str):
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    BASE_URL = os.getenv("BASE_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    # Primero eliminamos la sesión si ya existe
    await delete_session_if_exists(session_name)

    webhook_url = f"{BASE_URL}/webhook/{session_name}"

    payload = {
        "name": session_name,
        "start": True,
        "config": {
            "metadata": {
                "user.id": organization_id,
                "driver": driver
            },
            "proxy": None,
            "debug": False,
            "noweb": {
                "store": {
                    "enabled": True,
                    "fullSync": False
                }
            },
            "webhooks": [
                {
                    "url": webhook_url,
                    "events": ["message", "session.status"],
                    "hmac": None,
                    "retries": None,
                    "customHeaders": [
                        {"name": "x-org-token", "value": organization_id},
                        {"name": "driver", "value": driver}
                    ]
                }
            ]
        }
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(f"{WAHA_API_URL}/api/sessions", json=payload) as response:
            response.raise_for_status()
            return await response.json()



async def get_qr_code_from_waha(session_name: str):
    WAHA_API_URL = os.getenv("WAHA_API_URL")
    if not WAHA_API_URL:
        raise ValueError("WAHA_API_URL is not set")

    qr_url = f"{WAHA_API_URL}/api/{session_name}/auth/qr?format=image"

    async with aiohttp.ClientSession() as session:
        headers = {"Accept": "image/png"}
        async with session.get(qr_url, headers=headers) as response:
            response.raise_for_status()
            return await response.read()