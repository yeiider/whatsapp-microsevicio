from datetime import datetime

def extract_message_type_and_content(message_data: dict):
    msg = message_data.get("message", {})

    if "conversation" in msg:
        return "text", {"text": msg["conversation"]}
    elif "imageMessage" in msg:
        return "image", {"url": msg["imageMessage"].get("url"), "caption": msg["imageMessage"].get("caption", "")}
    elif "audioMessage" in msg:
        return "audio", {"url": msg["audioMessage"].get("url"), "duration": msg["audioMessage"].get("seconds")}
    elif "videoMessage" in msg:
        return "video", {"url": msg["videoMessage"].get("url"), "caption": msg["videoMessage"].get("caption", "")}
    elif "documentMessage" in msg:
        return "file", {"url": msg["documentMessage"].get("url"), "filename": msg["documentMessage"].get("fileName")}
    elif "interactiveMessage" in msg:
        return "interactive", msg["interactiveMessage"]
    elif "eventMessage" in msg:
        return "event", msg["eventMessage"]
    else:
        return "unknown", msg

def normalize_waha_message(payload):
    contact = payload["_chat"]
    message = payload["lastMessage"]
    message_data = message["_data"]

    message_type, content = extract_message_type_and_content(message_data)

    return {
        "contact": {
            "id": contact["id"],
            "name": contact.get("name", ""),
            "picture": payload.get("picture", "")
        },
        "message": {
            "from": message["from"],
            "fromMe": message["fromMe"],
            "body": message.get("body", ""),
            "timestamp": datetime.fromtimestamp(message["timestamp"]),
            "message_type": message_type,
            "content": content
        }
    }