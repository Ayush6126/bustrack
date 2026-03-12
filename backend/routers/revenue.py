# ============================================
# routers/revenue.py
# Revenue calculation + reporting
# ============================================

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import date, timedelta

from services.database import get_db

router = APIRouter()

# Fare structure (paise/km or fixed)
TICKET_FARES = {
    "full":        {"type": "fixed", "amount": 20.0},
    "half":        {"type": "fixed", "amount": 10.0},
    "pass":        {"type": "fixed", "amount": 0.0},   # monthly pass
    "concession":  {"type": "fixed", "amount": 10.0},  # student/disabled
    "senior":      {"type": "fixed", "amount": 10.0},
    "ticketless":  {"type": "fixed", "amount": 0.0},   # no revenue = loss
}


def calculate_fare(ticket_type: str, distance_km: float = None) -> float:
    fare_info = TICKET_FARES.get(ticket_type, {"type": "fixed", "amount": 20.0})
    if fare_info["type"] == "per_km" and distance_km:
        return round(fare_info["rate"] * distance_km, 2)
    return fare_info["amount"]


@router.get("/summary/{trip_id}")
async def get_trip_revenue(trip_id: str, db: AsyncSession = Depends(get_db)):
    """Full revenue breakdown for a trip"""
    
    result = await db.execute(text("""
        SELECT 
            ticket_type,
            COUNT(*) AS count,
            SUM(fare_charged) AS total_amount
        FROM passenger_events
        WHERE trip_id = :trip_id AND event_type = 'entry'
        GROUP BY ticket_type
        ORDER BY total_amount DESC
    """), {"trip_id": trip_id})
    
    rows = result.fetchall()
    breakdown = [
        {"ticket_type": r.ticket_type, "count": r.count, "amount": float(r.total_amount or 0)}
        for r in rows
    ]
    
    total = sum(b["amount"] for b in breakdown)
    ticketless = next((b for b in breakdown if b["ticket_type"] == "ticketless"), None)
    loss = (ticketless["count"] * 20) if ticketless else 0  # estimated loss at full fare

    return {
        "trip_id": trip_id,
        "total_revenue": total,
        "estimated_loss": loss,
        "breakdown": breakdown
    }


@router.get("/daily")
async def get_daily_revenue(target_date: str = None, db: AsyncSession = Depends(get_db)):
    """Total revenue for a specific date (default: today)"""
    
    d = target_date or str(date.today())
    result = await db.execute(text("""
        SELECT 
            t.id AS trip_id,
            b.bus_number,
            r.route_code,
            t.total_revenue,
            t.ticketless_loss,
            t.total_passengers,
            t.start_time,
            t.end_time
        FROM trips t
        JOIN buses b ON b.id = t.bus_id
        JOIN routes r ON r.id = t.route_id
        WHERE t.trip_date = :d AND t.status = 'completed'
        ORDER BY t.start_time
    """), {"d": d})
    
    rows = result.fetchall()
    trips = [dict(r._mapping) for r in rows]
    
    return {
        "date": d,
        "total_revenue": sum(t["total_revenue"] or 0 for t in trips),
        "total_passengers": sum(t["total_passengers"] or 0 for t in trips),
        "total_trips": len(trips),
        "trips": trips
    }


@router.get("/weekly")
async def get_weekly_revenue(db: AsyncSession = Depends(get_db)):
    """Last 7 days revenue comparison"""
    
    result = await db.execute(text("""
        SELECT 
            trip_date,
            SUM(total_revenue) AS revenue,
            SUM(total_passengers) AS passengers,
            COUNT(*) AS trips
        FROM trips
        WHERE trip_date >= CURRENT_DATE - INTERVAL '14 days'
            AND status = 'completed'
        GROUP BY trip_date
        ORDER BY trip_date
    """))
    
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


@router.get("/fare-calculator")
async def calculate_trip_fare(
    ticket_type: str = "full",
    from_stop: str = None,
    to_stop: str = None,
    route_code: str = "DL-501",
    db: AsyncSession = Depends(get_db)
):
    """Calculate fare between two stops"""
    
    if from_stop and to_stop:
        result = await db.execute(text("""
            SELECT 
                ABS(s2.fare_from_origin - s1.fare_from_origin) AS fare
            FROM stops s1
            JOIN routes r ON r.id = s1.route_id
            JOIN stops s2 ON s2.route_id = r.id
            WHERE r.route_code = :route_code
              AND s1.name ILIKE :from_stop
              AND s2.name ILIKE :to_stop
        """), {"route_code": route_code, "from_stop": f"%{from_stop}%", "to_stop": f"%{to_stop}%"})
        
        row = result.fetchone()
        base_fare = float(row.fare) if row else 20.0
    else:
        base_fare = 20.0

    multipliers = {"full": 1.0, "half": 0.5, "pass": 0.0, "concession": 0.5, "senior": 0.5, "ticketless": 0.0}
    final_fare = base_fare * multipliers.get(ticket_type, 1.0)
    
    return {
        "ticket_type": ticket_type,
        "from_stop": from_stop,
        "to_stop": to_stop,
        "base_fare": base_fare,
        "final_fare": final_fare
    }
