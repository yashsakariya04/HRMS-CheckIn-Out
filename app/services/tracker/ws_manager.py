"""
WebSocket connection manager for real-time tracker notifications.
Maintains a per-user set of active WebSocket connections.
"""
import uuid
from collections import defaultdict
from typing import Dict, Set

from fastapi import WebSocket


class WSConnectionManager:
    def __init__(self):
        # user_id -> set of active WebSocket connections
        self._connections: Dict[str, Set[WebSocket]] = defaultdict(set)

    async def connect(self, user_id: uuid.UUID, ws: WebSocket):
        await ws.accept()
        self._connections[str(user_id)].add(ws)

    def disconnect(self, user_id: uuid.UUID, ws: WebSocket):
        uid = str(user_id)
        self._connections[uid].discard(ws)
        if not self._connections[uid]:
            del self._connections[uid]

    async def send_to_user(self, user_id: uuid.UUID, payload: dict):
        uid = str(user_id)
        dead: Set[WebSocket] = set()
        for ws in list(self._connections.get(uid, [])):
            try:
                await ws.send_json(payload)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[uid].discard(ws)


ws_manager = WSConnectionManager()
