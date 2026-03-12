# ============================================
# ai/passenger_detector.py
# YOLO v8 Passenger Detection + Frame Streaming
# ============================================

import cv2
import numpy as np
import asyncio
import aiohttp
import time
import logging
from datetime import datetime
from typing import Optional
from dataclasses import dataclass, field

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

logger = logging.getLogger("bustrack.ai")
logging.basicConfig(level=logging.INFO)

API_BASE_URL       = "http://localhost:8000/api"
YOLO_MODEL_PATH    = "yolov8n.pt"
CONFIDENCE_THRESHOLD = 0.5
PERSON_CLASS_ID    = 0
FRAME_SKIP         = 2
COUNTING_LINE_Y    = 0.75   # line at 75% of frame height (lower = easier to cross)


@dataclass
class TrackedPerson:
    track_id: int
    positions: list = field(default_factory=list)
    crossed_line: bool = False
    direction: Optional[str] = None
    first_seen: float = field(default_factory=time.time)
    last_seen:  float = field(default_factory=time.time)


class PassengerDetector:
    def __init__(self, camera_id, camera_source, trip_id,
                 enable_privacy_blur=True, stream_to_dashboard=True):
        self.camera_id           = camera_id
        self.camera_source       = camera_source
        self.trip_id             = trip_id
        self.enable_privacy_blur = enable_privacy_blur
        self.stream_to_dashboard = stream_to_dashboard

        self.model           = None
        self.tracked_persons = {}
        self.entry_count     = 0
        self.exit_count      = 0
        self.frame_count     = 0
        self.running         = False

    def load_model(self):
        if not YOLO_AVAILABLE:
            raise RuntimeError("pip install ultralytics")
        logger.info("Loading YOLO model...")
        self.model = YOLO(YOLO_MODEL_PATH)
        logger.info("✅ YOLO model loaded")

    def blur_face(self, frame, bbox):
        x1, y1, x2, y2 = bbox
        face_y2 = y1 + int((y2 - y1) * 0.35)
        region = frame[y1:face_y2, x1:x2]
        if region.size > 0:
            frame[y1:face_y2, x1:x2] = cv2.GaussianBlur(region, (99, 99), 30)
        return frame

    def determine_direction(self, track):
        if len(track.positions) < 4:
            return None
        first_y = np.mean([p[1] for p in track.positions[:3]])
        last_y  = np.mean([p[1] for p in track.positions[-3:]])
        delta   = last_y - first_y
        if abs(delta) < 15:
            return None
        return "entry" if delta > 0 else "exit"

    def classify_ticket(self):
        import random
        r = random.random()
        if r < 0.75:   return "full",       20.0
        elif r < 0.85: return "half",       10.0
        elif r < 0.90: return "concession", 10.0
        elif r < 0.93: return "senior",     10.0
        elif r < 0.96: return "pass",        0.0
        else:          return "ticketless",  0.0

    async def send_event(self, session, event_type, ticket_type, fare, confidence):
        payload = {
            "trip_id":          self.trip_id,
            "event_type":       event_type,
            "ticket_type":      ticket_type,
            "fare_charged":     fare,
            "camera_id":        self.camera_id,
            "confidence_score": confidence,
        }
        try:
            async with session.post(
                f"{API_BASE_URL}/passengers/event", json=payload,
                timeout=aiohttp.ClientTimeout(total=2)
            ) as resp:
                if resp.status == 200:
                    logger.info(f"📡 {event_type} | {ticket_type} | ₹{fare}")
        except Exception as e:
            logger.error(f"Event send failed: {e}")

    def draw_overlay(self, frame, results):
        h, w = frame.shape[:2]
        line_y = int(h * COUNTING_LINE_Y)

        # Counting line
        cv2.line(frame, (0, line_y), (w, line_y), (0, 220, 255), 3)
        cv2.putText(frame, "COUNTING LINE", (10, line_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 2)

        # Stats overlay — dark background
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (280, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.5, frame, 0.5, 0, frame)

        stats = [
            f"CAMERA: {self.camera_id.upper()}",
            f"ENTRIES: {self.entry_count}",
            f"EXITS:   {self.exit_count}",
            f"TRIP:    {self.trip_id[:8]}...",
        ]
        for i, txt in enumerate(stats):
            cv2.putText(frame, txt, (10, 25 + i * 24),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 80), 2)

        # Bounding boxes
        if results and results[0].boxes is not None:
            for box in results[0].boxes:
                if int(box.cls[0]) != PERSON_CLASS_ID:
                    continue
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                if self.enable_privacy_blur:
                    frame = self.blur_face(frame, (x1, y1, x2, y2))
                # Orange box
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 165, 255), 2)
                cv2.putText(frame, f"P {conf:.2f}", (x1, y1 - 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 165, 255), 2)

        # REC indicator
        cv2.circle(frame, (w - 20, 18), 8, (0, 0, 255), -1)
        cv2.putText(frame, "REC", (w - 55, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Timestamp
        ts = datetime.now().strftime("%H:%M:%S")
        cv2.putText(frame, ts, (w - 90, h - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
        return frame

    async def push_frame_to_dashboard(self, frame):
        """Encode frame as JPEG and push to stream router"""
        try:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            from routers.stream import set_latest_frame
            set_latest_frame(self.camera_id, buf.tobytes())
        except Exception:
            pass

    async def run(self):
        self.load_model()
        cap = cv2.VideoCapture(self.camera_source)
        if not cap.isOpened():
            logger.error(f"Cannot open camera: {self.camera_source}")
            return

        logger.info(f"🎥 Camera {self.camera_id} started")
        self.running = True

        async with aiohttp.ClientSession() as session:
            while self.running:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(0.1)
                    continue

                self.frame_count += 1
                if self.frame_count % FRAME_SKIP != 0:
                    continue

                results = self.model.track(
                    source=frame, persist=True,
                    classes=[PERSON_CLASS_ID],
                    conf=CONFIDENCE_THRESHOLD,
                    verbose=False,
                )

                h, w = frame.shape[:2]
                line_y = int(h * COUNTING_LINE_Y)

                if results[0].boxes is not None and results[0].boxes.id is not None:
                    for box, tid in zip(results[0].boxes, results[0].boxes.id):
                        track_id = int(tid)
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2

                        if track_id not in self.tracked_persons:
                            self.tracked_persons[track_id] = TrackedPerson(track_id=track_id)
                        track = self.tracked_persons[track_id]
                        track.positions.append((cx, cy))
                        track.last_seen = time.time()

                        if len(track.positions) >= 2 and not track.crossed_line:
                            prev_cy = track.positions[-2][1]
                            crossed = (prev_cy < line_y <= cy) or (prev_cy > line_y >= cy)
                            if crossed:
                                direction = self.determine_direction(track)
                                if direction:
                                    track.crossed_line = True
                                    ticket, fare = self.classify_ticket()
                                    conf = float(box.conf[0])
                                    if direction == "entry": self.entry_count += 1
                                    else:                    self.exit_count  += 1
                                    await self.send_event(session, direction, ticket, fare, conf)

                # Cleanup stale tracks
                now = time.time()
                stale = [tid for tid, t in self.tracked_persons.items() if now - t.last_seen > 5]
                for tid in stale:
                    del self.tracked_persons[tid]

                # Draw overlay
                frame = self.draw_overlay(frame, results)

                # Push to dashboard WebSocket
                if self.stream_to_dashboard:
                    await self.push_frame_to_dashboard(frame)

                # Show local window too
                cv2.imshow(f"BusTrack - {self.camera_id}", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                await asyncio.sleep(0)

        cap.release()
        cv2.destroyAllWindows()
        logger.info(f"Camera stopped | Entries:{self.entry_count} Exits:{self.exit_count}")

    def stop(self):
        self.running = False


async def run_all_cameras(trip_id: str):
    cameras = [
        PassengerDetector("front_door", 0, trip_id, stream_to_dashboard=True),
    ]
    await asyncio.gather(*[cam.run() for cam in cameras])


if __name__ == "__main__":
    import sys
    trip_id = sys.argv[1] if len(sys.argv) > 1 else "test-trip-001"
    print(f"🚌 Starting AI detection for trip: {trip_id}")
    asyncio.run(run_all_cameras(trip_id))
