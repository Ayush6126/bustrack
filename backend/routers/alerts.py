# ============================================
# routers/alerts.py
# ============================================

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
import uuid

from services.database import get_db

router = APIRouter()


class AlertCreate(BaseModel):
    trip_id: str
    bus_id: str
    alert_type: str   # overcrowding, ticketless, emergency, system
    severity: str     # info, warning, danger, critical
    message: str


@router.post("/")
async def create_alert(alert: AlertCreate, db: AsyncSession = Depends(get_db)):
    alert_id = str(uuid.uuid4())
    await db.execute(text("""
        INSERT INTO alerts (id, trip_id, bus_id, alert_type, severity, message)
        VALUES (:id, :trip_id, :bus_id, :alert_type, :severity, :message)
    """), {
        "id": alert_id, "trip_id": alert.trip_id, "bus_id": alert.bus_id,
        "alert_type": alert.alert_type, "severity": alert.severity, "message": alert.message
    })
    return {"alert_id": alert_id}


@router.get("/active/{trip_id}")
async def get_active_alerts(trip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("""
        SELECT * FROM alerts
        WHERE trip_id = :trip_id AND is_resolved = FALSE
        ORDER BY created_at DESC
    """), {"trip_id": trip_id})
    return [dict(r._mapping) for r in result.fetchall()]


@router.patch("/resolve/{alert_id}")
async def resolve_alert(alert_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(text("""
        UPDATE alerts SET is_resolved = TRUE, resolved_at = NOW()
        WHERE id = :id
    """), {"id": alert_id})
    return {"status": "resolved"}


# ============================================
# routers/cameras.py
# ============================================
from fastapi import APIRouter as CameraAPIRouter
from sqlalchemy.ext.asyncio import AsyncSession as CamSession
from sqlalchemy import text as cam_text
from services.database import get_db as cam_get_db
from fastapi import Depends as CamDepends

camera_router = CameraAPIRouter()

# Create a separate router object for cameras module
from fastapi import APIRouter
router2 = APIRouter()


@router2.get("/status")
async def get_camera_status(db: AsyncSession = Depends(get_db)):
    """Get status of all cameras"""
    result = await db.execute(text("""
        SELECT cs.*, b.bus_number
        FROM camera_sessions cs
        JOIN buses b ON b.id = cs.bus_id
        ORDER BY cs.started_at DESC
    """))
    rows = result.fetchall()
    if not rows:
        # Return mock status if no DB data
        return [
            {"camera_position": "front_door", "status": "online", "detections_today": 89},
            {"camera_position": "rear_door",  "status": "online", "detections_today": 67},
            {"camera_position": "interior",   "status": "online", "detections_today": 0},
        ]
    return [dict(r._mapping) for r in rows]


@router2.post("/heartbeat/{camera_id}")
async def camera_heartbeat(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Camera sends heartbeat every 30s to confirm it's alive"""
    await db.execute(text("""
        UPDATE camera_sessions 
        SET last_heartbeat = NOW(), status = 'online'
        WHERE id = :camera_id
    """), {"camera_id": camera_id})
    return {"status": "ok"}
