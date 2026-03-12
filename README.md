# 🚌 BusTrack AI — Complete Setup Guide
## Local Machine (Development) — Windows/Mac/Linux

---

## 📁 Project Structure

```
bustrack/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── routers/
│   │   ├── passengers.py          # Passenger events + WebSocket
│   │   ├── revenue.py             # Revenue + fare calculation
│   │   ├── trips.py               # Trip management
│   │   ├── alerts.py              # Alert system
│   │   └── cameras.py             # Camera status
│   ├── services/
│   │   ├── database.py            # Async PostgreSQL connection
│   │   └── websocket_manager.py   # Real-time broadcast manager
│   └── ai/
│       └── passenger_detector.py  # YOLO v8 detection engine
├── database/
│   └── schema.sql                 # PostgreSQL schema + seed data
├── frontend/
│   └── useBusTrackWebSocket.js    # React WebSocket hook
├── docker-compose.yml             # One-command full stack
└── README.md
```

---

## 🚀 OPTION A — Docker (Easiest, Recommended)

### Prerequisites
- Install [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Steps

```bash
# 1. Clone / navigate to project
cd bustrack/

# 2. Start everything (DB + Backend + Frontend + pgAdmin)
docker-compose up -d

# 3. Check all services running
docker-compose ps

# 4. View backend logs
docker-compose logs -f backend

# 5. Open in browser
#    Dashboard:  http://localhost:3000
#    API Docs:   http://localhost:8000/docs
#    pgAdmin DB: http://localhost:5050
#                Email: admin@bustrack.local  Password: admin123
```

### Stop everything
```bash
docker-compose down
# To also delete database data:
docker-compose down -v
```

---

## 🐍 OPTION B — Manual Setup (No Docker)

### Step 1: PostgreSQL Setup

```bash
# Install PostgreSQL 16
# Ubuntu/Debian:
sudo apt install postgresql postgresql-contrib

# macOS (Homebrew):
brew install postgresql@16

# Windows: Download from https://www.postgresql.org/download/windows/

# Create database
sudo -u postgres psql
CREATE USER bustrack WITH PASSWORD 'bustrack123';
CREATE DATABASE bustrack_db OWNER bustrack;
GRANT ALL PRIVILEGES ON DATABASE bustrack_db TO bustrack;
\q

# Run schema
psql -U bustrack -d bustrack_db -f database/schema.sql
```

### Step 2: Backend Setup

```bash
cd backend/

# Create virtual environment
python -m venv venv

# Activate
# Linux/Mac:
source venv/bin/activate
# Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set environment variable
export DATABASE_URL="postgresql+asyncpg://bustrack:bustrack123@localhost:5432/bustrack_db"
# Windows PowerShell:
# $env:DATABASE_URL="postgresql+asyncpg://bustrack:bustrack123@localhost:5432/bustrack_db"

# Start backend
python main.py
# Backend runs at: http://localhost:8000
# API Docs at:     http://localhost:8000/docs
```

### Step 3: Frontend Setup

```bash
cd frontend/

# Install Node.js 20+ from https://nodejs.org
# Then:
npm install

# Create .env.local
echo "VITE_API_URL=http://localhost:8000" > .env.local
echo "VITE_WS_URL=ws://localhost:8000"   >> .env.local

# Start frontend
npm run dev
# Frontend at: http://localhost:3000
```

### Step 4: AI Detection (With Camera)

```bash
cd backend/

# Install AI dependencies (if not in requirements already)
pip install ultralytics opencv-python

# Run detector (uses webcam index 0 by default)
# First argument = trip_id from active trip
python ai/passenger_detector.py "YOUR-TRIP-ID-HERE"

# YOLO model (yolov8n.pt) downloads automatically (~6MB) on first run
```

---

## 🔌 API Quick Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/trips/active` | All running trips |
| POST | `/api/trips/start` | Start new trip |
| POST | `/api/trips/end/{id}` | End trip |
| GET | `/api/passengers/current-occupancy/{trip_id}` | Live count |
| POST | `/api/passengers/event` | Record entry/exit (AI calls this) |
| GET | `/api/revenue/daily` | Today's revenue |
| GET | `/api/revenue/weekly` | 7-day comparison |
| GET | `/api/alerts/active/{trip_id}` | Active alerts |
| WS | `/api/passengers/ws/{trip_id}` | Live WebSocket stream |
| WS | `/api/passengers/ws/global/dashboard` | All-buses stream |

---

## 🧪 Test the API (Without Camera)

```bash
# 1. Start a trip
curl -X POST http://localhost:8000/api/trips/start \
  -H "Content-Type: application/json" \
  -d '{"bus_id": "BUS-UUID-HERE", "route_id": "ROUTE-UUID-HERE"}'

# 2. Simulate passenger boarding
curl -X POST http://localhost:8000/api/passengers/event \
  -H "Content-Type: application/json" \
  -d '{
    "trip_id": "TRIP-ID-HERE",
    "event_type": "entry",
    "ticket_type": "full",
    "fare_charged": 20.0,
    "camera_id": "front_door",
    "confidence_score": 0.95
  }'

# 3. Check occupancy
curl http://localhost:8000/api/passengers/current-occupancy/TRIP-ID-HERE

# 4. Check revenue
curl http://localhost:8000/api/revenue/summary/TRIP-ID-HERE
```

---

## 📷 Camera Configuration

### USB Webcam (Testing)
```python
# In ai/passenger_detector.py, cameras list:
PassengerDetector("front_door", 0, trip_id)   # /dev/video0
PassengerDetector("rear_door",  1, trip_id)   # /dev/video1
```

### IP Camera (RTSP — Production)
```python
PassengerDetector("front_door", "rtsp://admin:pass@192.168.1.100:554/stream1", trip_id)
PassengerDetector("rear_door",  "rtsp://admin:pass@192.168.1.101:554/stream1", trip_id)
```

### Raspberry Pi Camera (On-Bus Edge)
```python
PassengerDetector("front_door", "picam://", trip_id)
# or use libcamera:
PassengerDetector("front_door", "libcamera://", trip_id)
```

---

## 🔧 Common Issues & Fixes

| Problem | Fix |
|---------|-----|
| `asyncpg.exceptions.ConnectionRefusedError` | PostgreSQL not running. Start it: `sudo systemctl start postgresql` |
| `ModuleNotFoundError: ultralytics` | Run: `pip install ultralytics` |
| YOLO model not downloading | Check internet connection. Manual download: `yolo export model=yolov8n.pt` |
| Camera index error | Try index 0, 1, 2. On Linux check: `ls /dev/video*` |
| WebSocket not connecting | Make sure backend is on port 8000 and CORS is enabled |
| Port 5432 already in use | Another PostgreSQL instance running. Stop it or change port in docker-compose.yml |

---

## 📊 Connect Frontend Dashboard to Live Data

In the React dashboard, add this hook:

```jsx
import { useBusTrackWebSocket } from './useBusTrackWebSocket';

function Dashboard() {
  const { connected, occupancy, revenueToday, alerts } = useBusTrackWebSocket("your-trip-id");

  return (
    <div>
      <div>🟢 {connected ? "Live" : "Reconnecting..."}</div>
      <div>Passengers: {occupancy.current} / {occupancy.capacity}</div>
      <div>Revenue: ₹{revenueToday}</div>
      <div>Alerts: {alerts.length}</div>
    </div>
  );
}
```

---

## 🚀 Next Level Features (Phase 2)

- [ ] SMS alerts via Twilio API
- [ ] PDF/Excel report generation  
- [ ] Mobile app (React Native)
- [ ] GPS tracking integration
- [ ] Passenger density heatmap inside bus (seat grid)
- [ ] Multi-city deployment
- [ ] Conductor tablet app

---

*BusTrack AI v1.0 | Built for Indian Public Transport*
