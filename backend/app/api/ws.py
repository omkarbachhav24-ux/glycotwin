from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ws_manager import manager

ws_router = APIRouter()


@ws_router.websocket("/ws/{patient_id}")
async def twin_socket(websocket: WebSocket, patient_id: str):
    """Live twin updates. The client receives one message per ingested event."""
    await manager.connect(patient_id, websocket)
    engine = websocket.app.state.engine
    try:
        if engine and patient_id in engine.twins:
            snap = engine.twins[patient_id].snapshot()
            snap["stream"] = engine.stream_status(patient_id)
            await manager.broadcast(patient_id, {"type": "snapshot", "snapshot": snap})
        while True:
            # Keeps the connection open. The client sends pings only.
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(patient_id, websocket)
    except Exception:
        await manager.disconnect(patient_id, websocket)
