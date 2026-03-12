# ============================================
# BUSTRACK AI - FastAPI Backend
# main.py
# ============================================

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from routers import passengers, revenue, trips, alerts, cameras
from services.websocket_manager import WebSocketManager
from services.database import init_db

# Global WebSocket manager
ws_manager = WebSocketManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚌 BusTrack AI Backend Starting...")
    await init_db()
    print("✅ Database connected")
    yield
    # Shutdown
    print("🛑 BusTrack AI Backend Shutting down...")

app = FastAPI(
    title="BusTrack AI API",
    description="Real-time Bus Passenger Monitoring System",
    version="1.0.0",
    lifespan=lifespan
)

# CORS - allow frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store ws_manager on app state so routers can access
app.state.ws_manager = ws_manager

# Include routers
app.include_router(passengers.router, prefix="/api/passengers", tags=["Passengers"])
app.include_router(revenue.router,    prefix="/api/revenue",    tags=["Revenue"])
app.include_router(trips.router,      prefix="/api/trips",      tags=["Trips"])
app.include_router(alerts.router,     prefix="/api/alerts",     tags=["Alerts"])
app.include_router(cameras.router,    prefix="/api/cameras",    tags=["Cameras"])

@app.get("/")
async def root():
    return {"message": "🚌 BusTrack AI API Running", "docs": "/docs"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
