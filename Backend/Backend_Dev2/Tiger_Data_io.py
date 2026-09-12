"""
CourierAI - Conexión a Tiger Data (Dev 2)
--------------------------------------------
Ajustado al esquema REAL creado por Dev 1 (ver SCRIPT_SQL.txt):

  - orders            -> demanda de pedidos (columnas en inglés + status en
                          mayúsculas: 'PENDIENTE', 'ACEPTADA', 'RECHAZADA',
                          'COMPLETADA', 'EXPIRADA'; agente asignado en
                          assigned_agent: 'BASELINE' | 'SMART')
  - v_orders          -> vista de compatibilidad con alias en español que
                          usamos para LEER (origen_lat, tarifa_base, etc.)
  - decisiones        -> log de decisiones del motor (lo que ya usábamos)
  - transactions      -> ledger financiero real (gross_fare, operational_cost,
                          net_profit) — separado del log de decisiones

Tiger Data está construida sobre PostgreSQL, así que la conexión sigue
siendo psycopg2 estándar; lo único que cambió es el SQL de las queries.
"""

import os
import json
from contextlib import contextmanager
from typing import List, Dict, Optional

import psycopg2
import psycopg2.extras

from Motor_Matematico import Order

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ---------------------------------------------------------------------------
# 1. CONEXIÓN
# ---------------------------------------------------------------------------

def _connection_string() -> str:
    conn_str = os.environ.get("TIGER_DATA_URL")
    if conn_str:
        return conn_str
    try:
        import streamlit as st
        if "TIGER_DATA_URL" in st.secrets:
            return st.secrets["TIGER_DATA_URL"]
    except Exception:
        pass
    raise RuntimeError(
        "Falta la cadena de conexión a Tiger Data. Configúrala con UNA de estas opciones:\n"
        "  1) export TIGER_DATA_URL='postgresql://usuario:pass@host:5432/db?sslmode=require'\n"
        "  2) Crea un archivo .env junto al código con: TIGER_DATA_URL=postgresql://...\n"
        "  3) Si usas Streamlit, crea .streamlit/secrets.toml con: TIGER_DATA_URL = \"postgresql://...\""
    )


@contextmanager
def get_connection():
    conn = psycopg2.connect(_connection_string())
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 2. LECTURA: pedidos pendientes -> objetos Order
#    Usamos v_orders (vista de compatibilidad de Dev 1) porque ya trae los
#    alias en español que necesita nuestro Order.
# ---------------------------------------------------------------------------

def leer_pedidos_pendientes(limit: int = 50) -> List[Order]:
    query = """
        SELECT order_id, origen_lat, origen_lon, destino_lat, destino_lon,
               tarifa_base, tiempo_limite_s,
               EXTRACT(EPOCH FROM timestamp_creacion) AS ts_epoch
        FROM v_orders
        WHERE estado = 'PENDIENTE'
        ORDER BY timestamp_creacion ASC
        LIMIT %s;
    """
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(query, (limit,))
            filas = cur.fetchall()

    return [
        Order(
            order_id=str(f["order_id"]),          # orders.id es entero -> str
            origen=(f["origen_lat"], f["origen_lon"]),
            destino=(f["destino_lat"], f["destino_lon"]),
            tarifa_base=float(f["tarifa_base"]),
            tiempo_limite_s=int(f["tiempo_limite_s"]),
            timestamp_creacion=float(f["ts_epoch"]),
        )
        for f in filas
    ]


# ---------------------------------------------------------------------------
# 3. ESCRITURA
# ---------------------------------------------------------------------------

_ACCION_A_STATUS = {
    "aceptado": "ACEPTADA",
    "rechazado": "RECHAZADA",
}

def registrar_decision(agente: str, entrada_log: Dict):
    """Inserta en 'decisiones' (log de razonamiento). agente debe ser
    'BASELINE' o 'SMART' para que quede consistente con el resto del esquema."""
    order_id = entrada_log.get("orden_id") or entrada_log.get("order_id")
    accion = entrada_log.get("accion")
    razon = entrada_log.get("razon")
    margen = entrada_log.get("margen") or entrada_log.get("valor")

    metadata = {k: v for k, v in entrada_log.items()
                if k not in ("orden_id", "order_id", "accion", "razon", "margen", "valor")}

    query = """
        INSERT INTO decisiones (order_id, agente, accion, razon, margen_neto, metadata)
        VALUES (%s, %s, %s, %s, %s, %s);
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (str(order_id) if order_id else None,
                                 agente, accion, razon, margen, json.dumps(metadata)))


def actualizar_estado_orden(order_id: str, accion: str, agente: str):
    """accion: 'aceptado' | 'rechazado' -> mapea a status real de la tabla orders.
    Escribimos sobre la tabla real (no la vista) porque ahí viven status y
    assigned_agent con sus nombres/valores originales."""
    nuevo_status = _ACCION_A_STATUS.get(accion)
    if nuevo_status is None:
        return  # 'batching' u otras acciones no cambian el status por sí solas

    query = """
        UPDATE orders
        SET status = %s, assigned_agent = %s, updated_at = now()
        WHERE id = %s;
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (nuevo_status, agente, int(order_id)))


def registrar_transaccion(order_id: str, agente: str, gross_fare: float,
                            operational_cost: float, net_profit: float):
    """Escribe en el ledger financiero real (tabla transactions). Se usa
    cuando una orden se COMPLETA (no solo se acepta), que es cuando de
    verdad se realiza la ganancia."""
    query = """
        INSERT INTO transactions (order_id, agent_type, gross_fare,
                                    operational_cost, net_profit)
        VALUES (%s, %s, %s, %s, %s);
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (int(order_id), agente, gross_fare,
                                 operational_cost, net_profit))


def sincronizar_log_completo(agente_state, agente_nombre: str):
    """agente_nombre debe ser 'BASELINE' o 'SMART'. Vuelca el log completo
    del AgentState: escribe el razonamiento en 'decisiones' y actualiza el
    status en 'orders'. El registro en 'transactions' se hace aparte, cuando
    la entrega se marca como COMPLETADA (ver registrar_transaccion)."""
    for entrada in agente_state.log:
        registrar_decision(agente_nombre, entrada)
        order_id = entrada.get("orden_id")
        accion = entrada.get("accion")
        if order_id and accion in ("aceptado", "rechazado"):
            actualizar_estado_orden(order_id, accion, agente_nombre)


# ---------------------------------------------------------------------------
# 4. DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from Motor_Matematico import SmartAgent

    pedidos = leer_pedidos_pendientes(limit=20)
    print(f"Leídos {len(pedidos)} pedidos pendientes de Tiger Data")

    agente = SmartAgent(posicion_inicial=(25.6714, -100.3096))
    agente.ejecutar_turno(pedidos)

    sincronizar_log_completo(agente.state, agente_nombre="SMART")
    print("Decisiones y estados sincronizados a Tiger Data")