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
