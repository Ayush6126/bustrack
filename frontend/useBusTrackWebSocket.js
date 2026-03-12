// ============================================
// hooks/useBusTrackWebSocket.js
// React hook — connects to FastAPI WebSocket
// Provides live passenger + revenue updates
// ============================================

import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAY_MS = 3000;

export function useBusTrackWebSocket(tripId = null) {
  const wsRef = useRef(null);
  const reconnectTimer = useRef(null);

  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);

  // Live state
  const [occupancy, setOccupancy] = useState({ current: 0, capacity: 54, percentage: 0 });
  const [revenueToday, setRevenueToday] = useState(0);
  const [alerts, setAlerts] = useState([]);
  const [passengerEvents, setPassengerEvents] = useState([]);

  const connect = useCallback(() => {
    const url = tripId
      ? `${WS_BASE}/api/passengers/ws/${tripId}`
      : `${WS_BASE}/api/passengers/ws/global/dashboard`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      console.log("🟢 BusTrack WebSocket connected");
      // Send ping every 30s to keep alive
      const pingInterval = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) ws.send("ping");
      }, 30000);
      ws._pingInterval = pingInterval;
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg.type === "pong") return;

        setLastEvent(msg);

        switch (msg.type) {
          case "PASSENGER_EVENT":
            setPassengerEvents((prev) => [msg.payload, ...prev].slice(0, 50));
            if (msg.payload.event_type === "entry") {
              setRevenueToday((prev) => prev + (msg.payload.fare_charged || 0));
            }
            break;

          case "OCCUPANCY_UPDATE":
            setOccupancy({
              current:    msg.payload.current,
              capacity:   msg.payload.capacity,
              percentage: msg.payload.percentage,
            });
            break;

          case "ALERT":
            setAlerts((prev) => [
              {
                id:       Date.now(),
                ...msg.payload,
                time:     new Date().toLocaleTimeString(),
                resolved: false,
              },
              ...prev,
            ].slice(0, 20));
            break;

          default:
            break;
        }
      } catch (e) {
        console.error("WS parse error:", e);
      }
    };

    ws.onclose = () => {
      setConnected(false);
      clearInterval(ws._pingInterval);
      console.log("🔴 WebSocket disconnected, reconnecting...");
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY_MS);
    };

    ws.onerror = (err) => {
      console.error("WS error:", err);
      ws.close();
    };
  }, [tripId]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  const resolveAlert = useCallback((alertId) => {
    setAlerts((prev) =>
      prev.map((a) => (a.id === alertId ? { ...a, resolved: true } : a))
    );
  }, []);

  return {
    connected,
    occupancy,
    revenueToday,
    alerts: alerts.filter((a) => !a.resolved),
    passengerEvents,
    lastEvent,
    resolveAlert,
  };
}
