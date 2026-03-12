# ============================================
# services/websocket_manager.py
# Real-time broadcasting to all connected clients
# ============================================

from fastapi import WebSocket
from typing import Dict, List
import json
import asyncio
from datetime import datetime


class WebSocketManager:
    def __init__(self):
        # Dict: trip_id -> list of connected websockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
        # Global listeners (dashboard overview)
        self.global_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket, trip_id: str = None):
        await websocket.accept()
        if trip_id:
            if trip_id not in self.active_connections:
                self.active_connections[trip_id] = []
            self.active_connections[trip_id].append(websocket)
        else:
            self.global_connections.append(websocket)

    def disconnect(self, websocket: WebSocket, trip_id: str = None):
        if trip_id and trip_id in self.active_connections:
            self.active_connections[trip_id].remove(websocket)
        elif websocket in self.global_connections:
            self.global_connections.remove(websocket)

    async def broadcast_to_trip(self, trip_id: str, data: dict):
        """Send update to all clients watching a specific trip"""
        if trip_id not in self.active_connections:
            return
        message = json.dumps({**data, "timestamp": datetime.now().isoformat()})
        dead = []
        for ws in self.active_connections[trip_id]:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.active_connections[trip_id].remove(ws)

    async def broadcast_global(self, data: dict):
        """Send update to all dashboard clients"""
        message = json.dumps({**data, "timestamp": datetime.now().isoformat()})
        dead = []
        for ws in self.global_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.global_connections.remove(ws)

    async def send_passenger_event(self, trip_id: str, event: dict):
        await self.broadcast_to_trip(trip_id, {
            "type": "PASSENGER_EVENT",
            "payload": event
        })
        await self.broadcast_global({
            "type": "PASSENGER_EVENT",
            "trip_id": trip_id,
            "payload": event
        })

    async def send_alert(self, trip_id: str, alert: dict):
        await self.broadcast_to_trip(trip_id, {
            "type": "ALERT",
            "payload": alert
        })
        await self.broadcast_global({
            "type": "ALERT",
            "trip_id": trip_id,
            "payload": alert
        })

    async def send_occupancy_update(self, trip_id: str, occupancy: int, capacity: int):
        data = {
            "type": "OCCUPANCY_UPDATE",
            "payload": {
                "trip_id": trip_id,
                "current": occupancy,
                "capacity": capacity,
                "percentage": round((occupancy / capacity) * 100, 1)
            }
        }
        await self.broadcast_to_trip(trip_id, data)
        await self.broadcast_global(data)
