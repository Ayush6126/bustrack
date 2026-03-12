-- ============================================
-- BUSTRACK AI - PostgreSQL Database Schema
-- ============================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- BUSES TABLE
-- ============================================
CREATE TABLE buses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bus_number VARCHAR(20) UNIQUE NOT NULL,
    capacity INTEGER NOT NULL DEFAULT 54,
    route_id UUID,
    driver_name VARCHAR(100),
    driver_phone VARCHAR(15),
    status VARCHAR(20) DEFAULT 'inactive', -- active, inactive, maintenance
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ROUTES TABLE
-- ============================================
CREATE TABLE routes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_code VARCHAR(20) UNIQUE NOT NULL,  -- e.g. "DL-501"
    name VARCHAR(200) NOT NULL,
    origin VARCHAR(100) NOT NULL,
    destination VARCHAR(100) NOT NULL,
    total_distance_km DECIMAL(8,2),
    base_fare DECIMAL(6,2) NOT NULL DEFAULT 20.00,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- STOPS TABLE
-- ============================================
CREATE TABLE stops (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    route_id UUID REFERENCES routes(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    sequence_order INTEGER NOT NULL,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    distance_from_origin_km DECIMAL(8,2),
    fare_from_origin DECIMAL(6,2)
);

-- ============================================
-- TRIPS TABLE (each bus journey)
-- ============================================
CREATE TABLE trips (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bus_id UUID REFERENCES buses(id),
    route_id UUID REFERENCES routes(id),
    trip_date DATE NOT NULL DEFAULT CURRENT_DATE,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    status VARCHAR(20) DEFAULT 'scheduled', -- scheduled, active, completed, cancelled
    total_passengers INTEGER DEFAULT 0,
    total_revenue DECIMAL(10,2) DEFAULT 0.00,
    expected_revenue DECIMAL(10,2) DEFAULT 0.00,
    ticketless_count INTEGER DEFAULT 0,
    ticketless_loss DECIMAL(10,2) DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- PASSENGER EVENTS TABLE (entry/exit log)
-- ============================================
CREATE TABLE passenger_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID REFERENCES trips(id) ON DELETE CASCADE,
    stop_id UUID REFERENCES stops(id),
    event_type VARCHAR(10) NOT NULL, -- 'entry' or 'exit'
    ticket_type VARCHAR(20), -- full, half, pass, concession, senior, ticketless
    fare_charged DECIMAL(6,2) DEFAULT 0.00,
    camera_id VARCHAR(20), -- front_door, rear_door, interior
    confidence_score DECIMAL(4,3), -- AI detection confidence (0.000-1.000)
    timestamp TIMESTAMP DEFAULT NOW(),
    frame_snapshot_path VARCHAR(500) -- path to saved frame image
);

-- ============================================
-- OCCUPANCY SNAPSHOTS (every 30 seconds)
-- ============================================
CREATE TABLE occupancy_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID REFERENCES trips(id) ON DELETE CASCADE,
    current_occupancy INTEGER NOT NULL,
    capacity INTEGER NOT NULL,
    occupancy_percentage DECIMAL(5,2),
    latitude DECIMAL(10,8),
    longitude DECIMAL(11,8),
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- REVENUE TABLE (per trip summary)
-- ============================================
CREATE TABLE revenue_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID REFERENCES trips(id) ON DELETE CASCADE,
    ticket_type VARCHAR(20) NOT NULL,
    count INTEGER DEFAULT 0,
    amount DECIMAL(10,2) DEFAULT 0.00,
    recorded_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- ALERTS TABLE
-- ============================================
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    trip_id UUID REFERENCES trips(id),
    bus_id UUID REFERENCES buses(id),
    alert_type VARCHAR(30) NOT NULL, -- overcrowding, ticketless, emergency, system
    severity VARCHAR(10) NOT NULL,   -- info, warning, danger, critical
    message TEXT NOT NULL,
    is_resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- CAMERA SESSIONS TABLE
-- ============================================
CREATE TABLE camera_sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    bus_id UUID REFERENCES buses(id),
    camera_position VARCHAR(20) NOT NULL, -- front_door, rear_door, interior
    stream_url VARCHAR(500),
    status VARCHAR(20) DEFAULT 'offline', -- online, offline, error
    last_heartbeat TIMESTAMP,
    started_at TIMESTAMP DEFAULT NOW()
);

-- ============================================
-- INDEXES for performance
-- ============================================
CREATE INDEX idx_passenger_events_trip ON passenger_events(trip_id);
CREATE INDEX idx_passenger_events_timestamp ON passenger_events(timestamp);
CREATE INDEX idx_passenger_events_type ON passenger_events(event_type);
CREATE INDEX idx_occupancy_trip ON occupancy_snapshots(trip_id);
CREATE INDEX idx_occupancy_recorded ON occupancy_snapshots(recorded_at);
CREATE INDEX idx_trips_date ON trips(trip_date);
CREATE INDEX idx_trips_bus ON trips(bus_id);
CREATE INDEX idx_alerts_trip ON alerts(trip_id);
CREATE INDEX idx_alerts_unresolved ON alerts(is_resolved) WHERE is_resolved = FALSE;

-- ============================================
-- SAMPLE DATA
-- ============================================
INSERT INTO routes (route_code, name, origin, destination, total_distance_km, base_fare) VALUES
('DL-501', 'Central to Airport Express', 'Central Station', 'Airport Terminal', 42.5, 20.00),
('DL-302', 'City Loop', 'City Mall', 'Industrial Zone', 28.0, 15.00);

INSERT INTO stops (route_id, name, sequence_order, latitude, longitude, distance_from_origin_km, fare_from_origin)
SELECT id, 'Central Station',    1, 28.6319, 77.2195, 0.0,  0.0  FROM routes WHERE route_code='DL-501' UNION ALL
SELECT id, 'City Mall',          2, 28.6280, 77.2090, 5.2,  10.0 FROM routes WHERE route_code='DL-501' UNION ALL
SELECT id, 'University',         3, 28.6350, 77.1980, 12.1, 15.0 FROM routes WHERE route_code='DL-501' UNION ALL
SELECT id, 'Hospital',           4, 28.6410, 77.1870, 19.4, 20.0 FROM routes WHERE route_code='DL-501' UNION ALL
SELECT id, 'Airport Terminal',   5, 28.5562, 77.1000, 42.5, 50.0 FROM routes WHERE route_code='DL-501';

INSERT INTO buses (bus_number, capacity, driver_name, driver_phone, status) VALUES
('DL-1C-4892', 54, 'Ramesh Kumar', '+91-9876543210', 'active'),
('DL-1C-5103', 54, 'Suresh Singh', '+91-9876543211', 'active');
