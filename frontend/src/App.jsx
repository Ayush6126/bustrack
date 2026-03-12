import { useState, useEffect, useCallback } from "react";
import { AreaChart, Area, BarChart, Bar, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const API = "http://localhost:8000/api";
const WS  = "ws://localhost:8000/api/passengers/ws/global/dashboard";

// ── WebSocket Hook ──────────────────────────────────────────────
function useRealtime() {
  const [connected, setConnected]       = useState(false);
  const [occupancy, setOccupancy]       = useState({ current: 0, capacity: 54, percentage: 0 });
  const [events, setEvents]             = useState([]);
  const [alerts, setAlerts]             = useState([]);
  const [revenue, setRevenue]           = useState(0);

  useEffect(() => {
    let ws, retryTimer;
    function connect() {
      ws = new WebSocket(WS);
      ws.onopen  = () => setConnected(true);
      ws.onclose = () => { setConnected(false); retryTimer = setTimeout(connect, 3000); };
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data);
        if (msg.type === "OCCUPANCY_UPDATE") setOccupancy(msg.payload);
        if (msg.type === "PASSENGER_EVENT") {
          setEvents(p => [{ ...msg.payload, time: new Date().toLocaleTimeString() }, ...p].slice(0, 30));
          if (msg.payload.event_type === "entry") setRevenue(p => p + (msg.payload.fare_charged || 0));
        }
        if (msg.type === "ALERT") setAlerts(p => [{ ...msg.payload, id: Date.now(), time: new Date().toLocaleTimeString() }, ...p].slice(0, 10));
      };
    }
    connect();
    return () => { clearTimeout(retryTimer); ws?.close(); };
  }, []);

  return { connected, occupancy, events, alerts, revenue };
}

// ── Helpers ─────────────────────────────────────────────────────
function OccupancyRing({ pct }) {
  const r = 48, c = 2 * Math.PI * r;
  const color = pct >= 85 ? "#ef4444" : pct >= 60 ? "#f59e0b" : "#10b981";
  return (
    <svg width="120" height="120" style={{ display: "block", margin: "0 auto" }}>
      <circle cx="60" cy="60" r={r} fill="none" stroke="#1e293b" strokeWidth="10" />
      <circle cx="60" cy="60" r={r} fill="none" stroke={color} strokeWidth="10"
        strokeDasharray={`${(pct/100)*c} ${c}`} strokeDashoffset={c*0.25}
        strokeLinecap="round" style={{ transition: "stroke-dasharray 0.8s ease" }} />
      <text x="60" y="56" textAnchor="middle" fill={color} fontSize="20" fontWeight="700" fontFamily="JetBrains Mono">{pct}%</text>
      <text x="60" y="72" textAnchor="middle" fill="#64748b" fontSize="9" fontFamily="DM Sans">OCCUPANCY</text>
    </svg>
  );
}

// ── Main App ─────────────────────────────────────────────────────
export default function App() {
  const { connected, occupancy, events, alerts, revenue } = useRealtime();
  const [tab, setTab]           = useState("live");
  const [theme, setTheme]       = useState("dark");
  const [trips, setTrips]       = useState([]);
  const [activeTripId, setActiveTripId] = useState(null);
  const [hourlyData, setHourlyData]     = useState([]);
  const [revBreakdown, setRevBreakdown] = useState([]);
  const [time, setTime]         = useState(new Date());
  const [starting, setStarting] = useState(false);

  const dark = theme === "dark";
  const bg   = dark ? "#050d1a" : "#f0f4f8";
  const card = dark ? "#0d1829" : "#ffffff";
  const bdr  = dark ? "#1e3a5f" : "#e2e8f0";
  const txt  = dark ? "#e2e8f0" : "#1e293b";
  const muted= dark ? "#64748b" : "#94a3b8";

  // Clock
  useEffect(() => { const t = setInterval(() => setTime(new Date()), 1000); return () => clearInterval(t); }, []);

  // Load active trips
  const loadTrips = useCallback(async () => {
    try {
      const r = await fetch(`${API}/trips/active`);
      const d = await r.json();
      setTrips(d);
      if (d.length > 0 && !activeTripId) setActiveTripId(d[0].id);
    } catch {}
  }, [activeTripId]);

  useEffect(() => { loadTrips(); const t = setInterval(loadTrips, 5000); return () => clearInterval(t); }, []);

  // Load analytics when trip selected
  useEffect(() => {
    if (!activeTripId) return;
    fetch(`${API}/passengers/hourly-flow/${activeTripId}`).then(r => r.json()).then(setHourlyData).catch(() => {});
    fetch(`${API}/revenue/summary/${activeTripId}`).then(r => r.json()).then(d => setRevBreakdown(d.breakdown || [])).catch(() => {});
  }, [activeTripId]);

  // Start new trip
  async function startTrip() {
    setStarting(true);
    try {
      const r = await fetch(`${API}/trips/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bus_id: "DL-1C-4892", route_id: "DL-501" })
      });
      const d = await r.json();
      setActiveTripId(d.trip_id);
      await loadTrips();
    } catch (e) { alert("Error: " + e.message); }
    setStarting(false);
  }

  // Simulate passenger (for testing without camera)
  async function simulatePassenger(type = "entry", ticket = "full") {
    if (!activeTripId) return alert("Pehle trip start karo!");
    const fares = { full: 20, half: 10, concession: 10, senior: 10, pass: 0, ticketless: 0 };
    await fetch(`${API}/passengers/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        trip_id: activeTripId,
        event_type: type,
        ticket_type: ticket,
        fare_charged: fares[ticket] || 20,
        camera_id: "front_door",
        confidence_score: 0.97
      })
    });
  }

  const cardStyle = { background: card, border: `1px solid ${bdr}`, borderRadius: 16, padding: 20 };

  return (
    <div style={{ background: bg, minHeight: "100vh", color: txt, fontFamily: "'DM Sans', sans-serif" }}>

      {/* Header */}
      <div style={{ background: dark ? "#070f1e" : "#fff", borderBottom: `1px solid ${bdr}`, padding: "0 24px" }}>
        <div style={{ maxWidth: 1300, margin: "0 auto", display: "flex", alignItems: "center", justifyContent: "space-between", height: 60 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 36, height: 36, borderRadius: 10, background: "linear-gradient(135deg,#0ea5e9,#6366f1)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 18 }}>🚌</div>
            <div>
              <div style={{ fontFamily: "JetBrains Mono", fontWeight: 700, fontSize: 14, color: "#0ea5e9" }}>BUSTRACK AI</div>
              <div style={{ fontSize: 10, color: muted, letterSpacing: "0.1em" }}>LIVE MONITORING</div>
            </div>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
            {/* Connection status */}
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
              <div style={{ width: 8, height: 8, borderRadius: "50%", background: connected ? "#10b981" : "#ef4444", boxShadow: connected ? "0 0 8px #10b981" : "none" }} />
              <span style={{ color: connected ? "#10b981" : "#ef4444", fontFamily: "JetBrains Mono", fontWeight: 700 }}>{connected ? "LIVE" : "OFFLINE"}</span>
            </div>
            <div style={{ fontFamily: "JetBrains Mono", fontSize: 13, color: txt }}>{time.toLocaleTimeString()}</div>
            {/* Trip selector */}
            {trips.length > 0 && (
              <select value={activeTripId || ""} onChange={e => setActiveTripId(e.target.value)}
                style={{ background: card, border: `1px solid ${bdr}`, color: txt, padding: "4px 10px", borderRadius: 8, fontSize: 12, fontFamily: "JetBrains Mono" }}>
                {trips.map(t => <option key={t.id} value={t.id}>{t.bus_number} — {t.route_code}</option>)}
              </select>
            )}
            <button onClick={startTrip} disabled={starting}
              style={{ padding: "6px 16px", borderRadius: 8, border: "none", background: "linear-gradient(135deg,#0ea5e9,#6366f1)", color: "#fff", fontWeight: 700, cursor: "pointer", fontSize: 12 }}>
              {starting ? "..." : "＋ New Trip"}
            </button>
            <button onClick={() => setTheme(dark ? "light" : "dark")}
              style={{ width: 32, height: 32, borderRadius: 8, border: `1px solid ${bdr}`, background: "transparent", cursor: "pointer", fontSize: 15 }}>
              {dark ? "☀️" : "🌙"}
            </button>
          </div>
        </div>
      </div>

      <div style={{ maxWidth: 1300, margin: "0 auto", padding: 24 }}>

        {/* Tabs */}
        <div style={{ display: "flex", gap: 4, marginBottom: 24, background: card, borderRadius: 12, padding: 4, border: `1px solid ${bdr}`, width: "fit-content" }}>
          {["live", "analytics", "simulate"].map(t => (
            <button key={t} onClick={() => setTab(t)}
              style={{ padding: "7px 20px", borderRadius: 8, border: "none", cursor: "pointer", fontWeight: 600, fontSize: 13, textTransform: "capitalize", background: tab === t ? "linear-gradient(135deg,#0ea5e9,#6366f1)" : "transparent", color: tab === t ? "#fff" : muted, transition: "all 0.2s" }}>
              {t === "live" ? "🔴 Live" : t === "analytics" ? "📊 Analytics" : "🧪 Test/Simulate"}
            </button>
          ))}
        </div>

        {/* ── LIVE TAB ── */}
        {tab === "live" && (
          <>
            {/* KPI Row */}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 20 }}>
              {[
                { label: "LIVE PASSENGERS", val: occupancy.current, sub: `of ${occupancy.capacity} seats`, color: "#0ea5e9", icon: "👥" },
                { label: "SESSION REVENUE", val: `₹${revenue.toFixed(0)}`, sub: "This trip", color: "#10b981", icon: "💰" },
                { label: "OCCUPANCY", val: `${occupancy.percentage}%`, sub: occupancy.percentage >= 85 ? "⚠️ Near full!" : "Normal", color: occupancy.percentage >= 85 ? "#ef4444" : "#10b981", icon: "📊" },
                { label: "ALERTS", val: alerts.length, sub: alerts.length > 0 ? alerts[0]?.type || "Active" : "All clear", color: alerts.length > 0 ? "#ef4444" : "#10b981", icon: "🚨" },
              ].map((k, i) => (
                <div key={i} style={{ ...cardStyle, position: "relative", overflow: "hidden" }}>
                  <div style={{ position: "absolute", top: 0, right: 0, width: 70, height: 70, background: `radial-gradient(circle,${k.color}20,transparent 70%)` }} />
                  <div style={{ fontSize: 10, letterSpacing: "0.12em", color: muted, fontWeight: 600, marginBottom: 8 }}>{k.label}</div>
                  <div style={{ fontFamily: "JetBrains Mono", fontSize: 30, fontWeight: 700, color: k.color }}>{k.val}</div>
                  <div style={{ fontSize: 11, color: muted, marginTop: 6 }}>{k.sub}</div>
                </div>
              ))}
            </div>

            {/* Occupancy + Events */}
            <div style={{ display: "grid", gridTemplateColumns: "220px 1fr 300px", gap: 16 }}>
              {/* Ring */}
              <div style={{ ...cardStyle, textAlign: "center" }}>
                <div style={{ fontWeight: 700, marginBottom: 12 }}>Bus Capacity</div>
                <OccupancyRing pct={Math.round(occupancy.percentage)} />
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginTop: 12 }}>
                  <div style={{ background: dark ? "#0a1628" : "#f8fafc", borderRadius: 8, padding: "8px 4px", textAlign: "center" }}>
                    <div style={{ fontFamily: "JetBrains Mono", fontSize: 20, fontWeight: 700, color: "#10b981" }}>{occupancy.capacity - occupancy.current}</div>
                    <div style={{ fontSize: 10, color: muted }}>Free</div>
                  </div>
                  <div style={{ background: dark ? "#0a1628" : "#f8fafc", borderRadius: 8, padding: "8px 4px", textAlign: "center" }}>
                    <div style={{ fontFamily: "JetBrains Mono", fontSize: 20, fontWeight: 700, color: "#ef4444" }}>{occupancy.current}</div>
                    <div style={{ fontSize: 10, color: muted }}>Occupied</div>
                  </div>
                </div>
              </div>

              {/* Live event feed */}
              <div style={{ ...cardStyle }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div style={{ fontWeight: 700 }}>Live Event Feed</div>
                  <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11, color: "#10b981" }}>
                    <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#10b981", animation: "pulse 1.5s infinite" }} />
                    Real-time
                  </div>
                </div>
                <div style={{ maxHeight: 220, overflowY: "auto" }}>
                  {events.length === 0 ? (
                    <div style={{ textAlign: "center", color: muted, padding: "40px 0", fontSize: 13 }}>
                      Koi event nahi abhi...<br/>
                      <span style={{ fontSize: 11 }}>Simulate tab se test karo 👆</span>
                    </div>
                  ) : events.map((e, i) => (
                    <div key={i} style={{ display: "flex", alignItems: "center", gap: 10, padding: "8px 0", borderBottom: `1px solid ${bdr}` }}>
                      <div style={{ width: 28, height: 28, borderRadius: 8, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 14, background: e.event_type === "entry" ? "#10b98120" : "#ef444420" }}>
                        {e.event_type === "entry" ? "↓" : "↑"}
                      </div>
                      <div style={{ flex: 1 }}>
                        <div style={{ fontSize: 12, fontWeight: 600, color: e.event_type === "entry" ? "#10b981" : "#ef4444" }}>
                          {e.event_type === "entry" ? "Boarded" : "Alighted"} — {e.ticket_type}
                        </div>
                        <div style={{ fontSize: 10, color: muted }}>{e.camera_id} · {e.time}</div>
                      </div>
                      <div style={{ fontFamily: "JetBrains Mono", fontSize: 12, fontWeight: 700, color: "#10b981" }}>
                        {e.fare_charged > 0 ? `+₹${e.fare_charged}` : "—"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Alerts */}
              <div style={{ ...cardStyle }}>
                <div style={{ fontWeight: 700, marginBottom: 14 }}>🚨 Alerts</div>
                {alerts.length === 0 ? (
                  <div style={{ textAlign: "center", color: muted, padding: "40px 0", fontSize: 13 }}>✅ Sab theek hai!</div>
                ) : alerts.map(a => {
                  const c = { warning: "#f59e0b", danger: "#ef4444", info: "#0ea5e9", success: "#10b981" };
                  return (
                    <div key={a.id} style={{ padding: "10px 12px", borderRadius: 10, marginBottom: 8, background: `${c[a.severity] || "#0ea5e9"}15`, border: `1px solid ${c[a.severity] || "#0ea5e9"}30` }}>
                      <div style={{ fontSize: 12, fontWeight: 500 }}>{a.message}</div>
                      <div style={{ fontSize: 10, color: muted, marginTop: 3 }}>{a.time}</div>
                    </div>
                  );
                })}
              </div>
            </div>
          </>
        )}

        {/* ── ANALYTICS TAB ── */}
        {tab === "analytics" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div style={{ ...cardStyle }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Hourly Passenger Flow</div>
              <div style={{ fontSize: 12, color: muted, marginBottom: 20 }}>Active trip — entries vs exits</div>
              {hourlyData.length === 0 ? (
                <div style={{ textAlign: "center", color: muted, padding: "60px 0" }}>Data aane do... passengers board karwao pehle</div>
              ) : (
                <ResponsiveContainer width="100%" height={260}>
                  <BarChart data={hourlyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke={dark ? "#1e293b" : "#f1f5f9"} />
                    <XAxis dataKey="hour" tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                    <YAxis tick={{ fill: muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                    <Tooltip contentStyle={{ background: card, border: `1px solid ${bdr}`, borderRadius: 8 }} />
                    <Bar dataKey="boarded"  fill="#10b981" radius={[4,4,0,0]} name="Boarded" />
                    <Bar dataKey="alighted" fill="#ef4444" radius={[4,4,0,0]} name="Alighted" />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>

            <div style={{ ...cardStyle }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Revenue Breakdown</div>
              <div style={{ fontSize: 12, color: muted, marginBottom: 20 }}>By ticket type</div>
              {revBreakdown.length === 0 ? (
                <div style={{ textAlign: "center", color: muted, padding: "60px 0" }}>Koi revenue data nahi abhi</div>
              ) : revBreakdown.map((b, i) => {
                const colors = ["#0ea5e9","#10b981","#f59e0b","#8b5cf6","#ef4444","#06b6d4"];
                const max = Math.max(...revBreakdown.map(x => x.amount));
                return (
                  <div key={i} style={{ marginBottom: 14 }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
                      <span style={{ fontSize: 13, textTransform: "capitalize" }}>{b.ticket_type}</span>
                      <span style={{ fontFamily: "JetBrains Mono", fontSize: 13, fontWeight: 700, color: colors[i % colors.length] }}>₹{b.amount} ({b.count}x)</span>
                    </div>
                    <div style={{ height: 6, background: dark ? "#1e293b" : "#f1f5f9", borderRadius: 4 }}>
                      <div style={{ width: `${max > 0 ? (b.amount / max) * 100 : 0}%`, height: "100%", background: colors[i % colors.length], borderRadius: 4, transition: "width 0.8s ease" }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── SIMULATE TAB ── */}
        {tab === "simulate" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
            <div style={{ ...cardStyle }}>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>🧪 Manual Test Panel</div>
              <div style={{ fontSize: 12, color: muted, marginBottom: 20 }}>Camera ke bina passengers simulate karo</div>

              <div style={{ fontWeight: 600, marginBottom: 10, fontSize: 13, color: muted }}>BOARDING (Entry)</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 24 }}>
                {[["Full Ticket", "full", "#0ea5e9"], ["Half Ticket", "half", "#8b5cf6"], ["Concession", "concession", "#f59e0b"], ["Senior", "senior", "#06b6d4"], ["Pass", "pass", "#10b981"], ["Ticketless ⚠️", "ticketless", "#ef4444"]].map(([label, type, color]) => (
                  <button key={type} onClick={() => simulatePassenger("entry", type)}
                    style={{ padding: "12px 8px", borderRadius: 10, border: `2px solid ${color}40`, background: `${color}15`, color, fontWeight: 700, cursor: "pointer", fontSize: 12, transition: "all 0.15s" }}
                    onMouseOver={e => e.target.style.background = `${color}30`}
                    onMouseOut={e => e.target.style.background = `${color}15`}>
                    ↓ {label}
                  </button>
                ))}
              </div>

              <div style={{ fontWeight: 600, marginBottom: 10, fontSize: 13, color: muted }}>ALIGHTING (Exit)</div>
              <button onClick={() => simulatePassenger("exit", "full")}
                style={{ width: "100%", padding: "12px", borderRadius: 10, border: `2px solid #ef444440`, background: "#ef444415", color: "#ef4444", fontWeight: 700, cursor: "pointer", fontSize: 13 }}>
                ↑ Passenger Utra (Exit)
              </button>

              <div style={{ marginTop: 20, padding: 14, borderRadius: 10, background: dark ? "#0a1628" : "#f8fafc", border: `1px solid ${bdr}` }}>
                <div style={{ fontSize: 12, color: muted, marginBottom: 6 }}>Active Trip ID:</div>
                <div style={{ fontFamily: "JetBrains Mono", fontSize: 11, color: "#0ea5e9", wordBreak: "break-all" }}>{activeTripId || "Koi trip active nahi — New Trip button dabao"}</div>
              </div>
            </div>

            <div style={{ ...cardStyle }}>
              <div style={{ fontWeight: 700, fontSize: 16, marginBottom: 6 }}>⚡ Bulk Test</div>
              <div style={{ fontSize: 12, color: muted, marginBottom: 20 }}>Ek saath bahut saare passengers simulate karo</div>

              {[
                ["Morning Rush (20 passengers)", 20, "full"],
                ["Mixed Crowd (10 full + 5 half)", null, null],
                ["Peak Hour (30 passengers)", 30, "full"],
                ["5 Ticketless Detected", 5, "ticketless"],
              ].map(([label, count, ticket], i) => (
                <button key={i} onClick={async () => {
                  if (!activeTripId) return alert("Pehle trip start karo!");
                  if (label.includes("Mixed")) {
                    for (let j = 0; j < 10; j++) await simulatePassenger("entry", "full");
                    for (let j = 0; j < 5; j++) await simulatePassenger("entry", "half");
                  } else {
                    for (let j = 0; j < count; j++) await simulatePassenger("entry", ticket);
                  }
                }}
                  style={{ width: "100%", padding: "14px 16px", borderRadius: 10, border: `1px solid ${bdr}`, background: dark ? "#0a1628" : "#f8fafc", color: txt, fontWeight: 600, cursor: "pointer", fontSize: 13, textAlign: "left", marginBottom: 10, transition: "all 0.15s" }}
                  onMouseOver={e => e.target.style.background = dark ? "#1e293b" : "#f1f5f9"}
                  onMouseOut={e => e.target.style.background = dark ? "#0a1628" : "#f8fafc"}>
                  ▶ {label}
                </button>
              ))}

              <div style={{ marginTop: 10, padding: 14, borderRadius: 10, background: "#0ea5e915", border: "1px solid #0ea5e930" }}>
                <div style={{ fontSize: 12, color: "#0ea5e9", fontWeight: 600, marginBottom: 4 }}>💡 Tip</div>
                <div style={{ fontSize: 12, color: muted }}>Events send karne ke baad "Live" tab pe jao — real-time update dikhega. WebSocket connected hona chahiye (LIVE green indicator).</div>
              </div>
            </div>
          </div>
        )}
      </div>

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 4px; }
        button:active { transform: scale(0.97); }
      `}</style>
    </div>
  );
}
