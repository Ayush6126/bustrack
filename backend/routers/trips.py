from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from pydantic import BaseModel
import uuid
from services.database import get_db

router = APIRouter()

class TripCreate(BaseModel):
    bus_id: str
    route_id: str

async def resolve_or_create_bus(bus_id, db):
    try:
        uuid.UUID(bus_id)
        return bus_id
    except ValueError:
        r = await db.execute(text("SELECT id FROM buses WHERE bus_number = :n"), {"n": bus_id})
        row = r.fetchone()
        if row:
            return str(row.id)
        new_id = str(uuid.uuid4())
        await db.execute(text("INSERT INTO buses (id, bus_number, capacity, status) VALUES (:id, :num, 54, 'active')"), {"id": new_id, "num": bus_id})
        return new_id

async def resolve_or_create_route(route_id, db):
    try:
        uuid.UUID(route_id)
        return route_id
    except ValueError:
        r = await db.execute(text("SELECT id FROM routes WHERE route_code = :c"), {"c": route_id})
        row = r.fetchone()
        if row:
            return str(row.id)
        new_id = str(uuid.uuid4())
        await db.execute(text("INSERT INTO routes (id, route_code, name, origin, destination, base_fare) VALUES (:id, :code, :name, 'Origin', 'Destination', 20.0)"), {"id": new_id, "code": route_id, "name": route_id})
        return new_id

@router.post("/start")
async def start_trip(trip: TripCreate, db: AsyncSession = Depends(get_db)):
    trip_id  = str(uuid.uuid4())
    bus_id   = await resolve_or_create_bus(trip.bus_id, db)
    route_id = await resolve_or_create_route(trip.route_id, db)
    await db.execute(text("INSERT INTO trips (id, bus_id, route_id, trip_date, start_time, status) VALUES (:id, :bus_id, :route_id, CURRENT_DATE, NOW(), 'active')"), {"id": trip_id, "bus_id": bus_id, "route_id": route_id})
    return {"trip_id": trip_id, "status": "active", "message": "Trip started"}

@router.post("/end/{trip_id}")
async def end_trip(trip_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(text("UPDATE trips SET status = 'completed', end_time = NOW() WHERE id = :trip_id"), {"trip_id": trip_id})
    return {"trip_id": trip_id, "status": "completed"}

@router.get("/active")
async def get_active_trips(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT t.id, b.bus_number, r.route_code, r.name as route_name, t.total_passengers, t.total_revenue, t.start_time FROM trips t JOIN buses b ON b.id = t.bus_id JOIN routes r ON r.id = t.route_id WHERE t.status = 'active' ORDER BY t.start_time DESC"))
    return [dict(r._mapping) for r in result.fetchall()]

@router.get("/{trip_id}")
async def get_trip_detail(trip_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT t.*, b.bus_number, b.capacity, r.route_code, r.name as route_name FROM trips t JOIN buses b ON b.id = t.bus_id JOIN routes r ON r.id = t.route_id WHERE t.id = :trip_id"), {"trip_id": trip_id})
    row = result.fetchone()
    return dict(row._mapping) if row else {}