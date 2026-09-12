-- ==========================================================
-- CourierAI: Esquema Relacional y Transaccional (Tiger Data)
-- Reto HackMTY 2026 - Track Infosys
-- ==========================================================

-- Tabla 1: Órdenes de pedidos
CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    origin_lat DOUBLE PRECISION NOT NULL,
    origin_lon DOUBLE PRECISION NOT NULL,
    dest_lat DOUBLE PRECISION NOT NULL,
    dest_lon DOUBLE PRECISION NOT NULL,
    origin_node_id BIGINT,
    dest_node_id BIGINT,
    base_fare NUMERIC(10, 2) NOT NULL,
    time_window_seconds INTEGER DEFAULT 600,
    expires_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(20) DEFAULT 'PENDIENTE' CHECK (status IN ('PENDIENTE', 'ACEPTADA', 'RECHAZADA', 'COMPLETADA', 'EXPIRADA')),
    assigned_agent VARCHAR(30) CHECK (assigned_agent IN ('BASELINE', 'SMART') OR assigned_agent IS NULL),
    route_path JSONB,
    event_type VARCHAR(30) DEFAULT 'normal',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla 2: Registro de posiciones y telemetría de repartidores en tiempo real
CREATE TABLE IF NOT EXISTS driver_logs (
    id SERIAL PRIMARY KEY,
    agent_type VARCHAR(30) NOT NULL CHECK (agent_type IN ('BASELINE', 'SMART')),
    current_lat DOUBLE PRECISION NOT NULL,
    current_lon DOUBLE PRECISION NOT NULL,
    current_node_id BIGINT,
    current_order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
    status VARCHAR(30) DEFAULT 'IDLE' CHECK (status IN ('IDLE', 'MOVING_TO_PICKUP', 'DELIVERING', 'RETURNING')),
    route_path JSONB,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Tabla 3: Ledger financiero de ganancias transaccionales
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    agent_type VARCHAR(30) NOT NULL CHECK (agent_type IN ('BASELINE', 'SMART')),
    gross_fare NUMERIC(10, 2) NOT NULL,
    operational_cost NUMERIC(10, 2) DEFAULT 0.00,
    net_profit NUMERIC(10, 2) NOT NULL,
    completed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Índices para optimizar lectura en tiempo real del simulador
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_driver_logs_agent ON driver_logs(agent_type, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_transactions_agent ON transactions(agent_type);

-- Tabla 4: Registro de decisiones de los agentes (Dev 2 / OR-Tools)
CREATE TABLE IF NOT EXISTS decisiones (
    id BIGSERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id) ON DELETE CASCADE,
    agente TEXT NOT NULL,
    accion TEXT NOT NULL,
    razon TEXT,
    margen_neto NUMERIC,
    metadata JSONB,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vista de compatibilidad v_orders para alias en español / inglés
CREATE OR REPLACE VIEW v_orders AS 
SELECT 
    id AS order_id,
    id,
    origin_lat AS origen_lat,
    origin_lat,
    origin_lon AS origen_lon,
    origin_lon,
    dest_lat AS destino_lat,
    dest_lat,
    dest_lon AS destino_lon,
    dest_lon,
    base_fare AS tarifa_base,
    base_fare,
    time_window_seconds AS tiempo_limite_s,
    time_window_seconds,
    status AS estado,
    status,
    event_type AS estado_ciudad,
    event_type,
    created_at AS timestamp_creacion,
    created_at
FROM orders;
