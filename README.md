# BusTrack

A passenger monitoring system for buses. Built with FastAPI, React, and YOLOv8.

## Features
- Real-time passenger counting via webcam
- Live dashboard with occupancy tracking
- Revenue and ticket management
- WebSocket-based live updates

## Tech Stack
- **Backend:** FastAPI, PostgreSQL, SQLAlchemy
- **Frontend:** React, Vite, Recharts
- **AI:** YOLOv8, OpenCV
- **Infra:** Docker, Docker Compose

## Setup
```bash
git clone https://github.com/Ayush6126/bustrack.git
cd bustrack
docker-compose up -d
```

## AI Detection
```bash
cd backend
pip install -r requirements.txt
python ai/passenger_detector.py <trip_id>
```