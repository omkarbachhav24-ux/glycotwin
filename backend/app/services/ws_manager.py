"""WebSocket fan out. One channel per patient, plus a broadcast of stream status.

competition.txt section 7: push updated predictions to the UI without a refresh.
"""
from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from datetime import datetime

from fastapi import WebSocket


def _default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"not serialisable: {type(obj)}")


class WebSocketManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, patient_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            self._rooms[patient_id].add(ws)

    async def disconnect(self, patient_id: str, ws: WebSocket) -> None:
        async with self._lock:
            self._rooms[patient_id].discard(ws)

    async def broadcast(self, patient_id: str, message: dict) -> None:
        payload = json.dumps(message, default=_default)
        async with self._lock:
            targets = list(self._rooms.get(patient_id, ()))
        dead = []
        for ws in targets:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._rooms[patient_id].discard(ws)

    def connection_count(self, patient_id: str) -> int:
        return len(self._rooms.get(patient_id, ()))


manager = WebSocketManager()
