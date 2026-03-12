# ============================================
# routers/passengers.py
# Passenger counting + WebSocket live feed
# ============================================

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

from services.database import get_db

router = APIRouter()


# ---- Pydantic Models ----

class PassengerEventIn(BaseModel):
    trip_id: str
    stop_id: Optional[str] = None
    event_type: str          # 'entry' or 'exit'
    ticket_type: str         # full, half, pass, concession, senior, ticketless
    fare_charged: float = 0.0
    camera_id: str           # front_door, rear_door, interior
    confidence_score: float = 1.0


# ---- REST Endpoints ----

@router.post("/event")
async def record_passenger_event(
    event: PassengerEventIn,
    db: AsyncSession = Depends(get_db)
):
    """Record a passenger entry or exit event (called by AI detection service)"""
    
    event_id = str(uuid.uuid4())
    
    await db.execute(text("""
        INSERT INTO passenger_events 
            (id, trip_id, stop_id, event_type, ticket_type, fare_charged, camera_id, confidence_score, timestamp)
        VALUES 
            (:id, :trip_id, :stop_id, :event_type, :ticket_type, :fare_charged, :camera_id, :confidence_score, NOW())
    """), {
        "id": event_id,
        "trip_id": event.trip_id,
        "stop_id": event.stop_id,
        "event_type": event.event_type,
        "ticket_type": event.ticket_type,
        "fare_charged": event.fare_charged,
        "camera_id": event.camera_id,
        "confidence_score": event.confidence_score,
    })

    # Update trip totals
    if event.event_type == "entry":
        await db.execute(text("""
            UPDATE trips 
            SET total_passengers = total_passengers + 1,
                total_revenue = total_revenue + :fare
            WHERE id = :trip_id
        """), {"trip_id": event.trip_id, "fare": event.fare_charged})

    # Broadcast via WebSocket
    from main import app
    ws_manager = app.state.ws_manager
    current = await get_current_occupancy(event.trip_id, db)
    await ws_manager.send_passenger_event(event.trip_id, {
        "event_type": event.event_type,
        "ticket_type": event.ticket_type,
        "camera_id": event.camera_id,
        "current_occupancy": current["occupancy"],
        "fare_charged": event.fare_charged,
    })

    # Check overcrowding
    if current["percentage"] >= 90:
        await ws_manager.send_alert(event.trip_id, {
            "type": "overcrowding",
            "severity": "danger",
            "message": f"Bus at {current['percentage']}% capacity!",
        })

    return {"status": "ok", "event_id": event_id}


@router.get("/current-occupancy/{trip_id}")
async def get_current_occupancy(trip_id: str, db: AsyncSession = Depends(get_db)):
    """Get live passenger count for a trip"""
    
    result = await db.execute(text("""
        SELECT 
            COALESCE(SUM(CASE WHEN event_type='entry' THEN 1 ELSE 0 END), 0) -
            COALESCE(SUM(CASE WHEN event_type='exit'  THEN 1 ELSE 0 END), 0) AS occupancy,
            b.capacity
        FROM passenger_events pe
        JOIN trips t ON t.id = pe.trip_id
        JOIN buses b ON b.id = t.bus_id
        WHERE pe.trip_id = :trip_id
        GROUP BY b.capacity
    """), {"trip_id": trip_id})
    
    row = result.fetchone()
    if not row:
        return {"occupancy": 0, "capacity": 54, "percentage": 0.0}
    
    pct = round((row.occupancy / row.capacity) * 100, 1)
    return {"occupancy": row.occupancy, "capacity": row.capacity, "percentage": pct}


@router.get("/hourly-flow/{trip_id}")
async def get_hourly_flow(trip_id: str, db: AsyncSession = Depends(get_db)):
    """Passenger entries grouped by hour"""
    
    result = await db.execute(text("""
        SELECT 
            TO_CHAR(timestamp, 'HH24:00') AS hour,
            COUNT(*) FILTER (WHERE event_type='entry') AS boarded,
            COUNT(*) FILTER (WHERE event_type='exit')  AS alighted
        FROM passenger_events
        WHERE trip_id = :trip_id
        GROUP BY hour
        ORDER BY hour
    """), {"trip_id": trip_id})
    
    return [{"hour": r.hour, "boarded": r.boarded, "alighted": r.alighted} 
            for r in result.fetchall()]


@router.get("/stop-wise/{trip_id}")
async def get_stop_wise_count(trip_id: str, db: AsyncSession = Depends(get_db)):
    """Passenger count per stop"""
    
    result = await db.execute(text("""
        SELECT 
            s.name AS stop_name,
            s.sequence_order,
            COUNT(*) FILTER (WHERE pe.event_type='entry') AS boarded,
            COUNT(*) FILTER (WHERE pe.event_type='exit')  AS alighted
        FROM passenger_events pe
        JOIN stops s ON s.id = pe.stop_id
        WHERE pe.trip_id = :trip_id
        GROUP BY s.name, s.sequence_order
        ORDER BY s.sequence_order
    """), {"trip_id": trip_id})
    
    return [dict(r._mapping) for r in result.fetchall()]


# ---- WebSocket Endpoint ----

@router.websocket("/ws/{trip_id}")
async def websocket_trip(websocket: WebSocket, trip_id: str):
    """
    WebSocket for live passenger updates.
    Frontend connects here to receive real-time events.
    
    Message types received:
      - PASSENGER_EVENT: entry/exit happened
      - OCCUPANCY_UPDATE: current count changed
      - ALERT: overcrowding or ticketless detection
    """
    from main import app
    ws_manager = app.state.ws_manager
    await ws_manager.connect(websocket, trip_id)
    try:
        while True:
            # Keep connection alive, receive any pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, trip_id)


@router.websocket("/ws/global/dashboard")
async def websocket_global(websocket: WebSocket):
    """WebSocket for main dashboard — receives all bus events"""
    from main import app
    ws_manager = app.state.ws_manager
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text('{"type":"pong"}')
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
