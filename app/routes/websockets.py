from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import Dict, List
from datetime import datetime
from bson import ObjectId

router = APIRouter()
active_connections: Dict[str, List[WebSocket]] = {}

def make_json_safe(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, dict):
        return {k: make_json_safe(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_safe(i) for i in obj]
    return obj

async def connect_websocket(websocket: WebSocket, organization_id: str):
    await websocket.accept()
    if organization_id not in active_connections:
        active_connections[organization_id] = []
    active_connections[organization_id].append(websocket)

def disconnect_websocket(websocket: WebSocket, organization_id: str):
    if organization_id in active_connections:
        active_connections[organization_id].remove(websocket)
        if not active_connections[organization_id]:
            del active_connections[organization_id]

async def emit_event(organization_id: str, event: dict):
    print(event)
    connections = active_connections.get(organization_id, [])
    safe_event = make_json_safe(event)
    for connection in connections:
        print(f"Emitting event to {connection.client}")
        await connection.send_json(safe_event)

@router.websocket("/ws/{organization_id}")
async def websocket_endpoint(websocket: WebSocket, organization_id: str):
    await connect_websocket(websocket, organization_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        disconnect_websocket(websocket, organization_id)
