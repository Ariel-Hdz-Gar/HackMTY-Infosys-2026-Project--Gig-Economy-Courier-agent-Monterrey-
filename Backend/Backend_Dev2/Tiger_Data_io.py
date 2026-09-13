"""
CourierAI - Conexión a Tiger Data (Dev 2)
--------------------------------------------
Ajustado al esquema REAL creado por Dev 1 (ver SCRIPT_SQL.txt), con los
ajustes que él confirmó después:

  - orders            -> demanda de pedidos (columnas en inglés + status en
                          mayúsculas: 'PENDIENTE', 'ACEPTADA', 'RECHAZADA',
                          'COMPLETADA', 'EXPIRADA'; agente asignado en
                          assigned_agent: 'BASELINE' | 'SMART')
  - v_orders          -> vista de compatibilidad con alias en español que
                          usamos para LEER (origen_lat, tarifa_base, etc.)
  - decisiones        -> log de decisiones del motor. order_id ahora es
                          INTEGER con FK real a orders.id (ya no TEXT), así
                          que se puede hacer JOIN directo sin castear.
  - transactions      -> ledger financiero real. NO lo escribimos nosotros:
                          Dev 1 tiene su propio simulator.py que detecta
                          cuando una orden pasa a 'ACEPTADA', simula el
                          tiempo de viaje, la marca 'COMPLETADA' e inserta
                          la transacción. Nuestro trabajo termina en poner
                          el status en 'ACEPTADA' o 'RECHAZADA'.

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
    """
    Busca la cadena de conexión en este orden (el primero que encuentre gana):
      1. TIGER_DATA_URL (si algún día se quiere una conexión separada solo
         para este módulo)
      2. DATABASE_URL (la variable que YA usa el resto del equipo -- ver
         Backend_Dev1/db/connection.py y Front-End/main.py -- así todos
         comparten un solo nombre de variable en el .env, sin duplicar)
      3. st.secrets, con cualquiera de los dos nombres, para Streamlit
    Nunca hardcodees la URL en el código ni la subas al repo.
    """
    conn_str = os.environ.get("TIGER_DATA_URL") or os.environ.get("DATABASE_URL")
    if conn_str:
        return conn_str
    try:
        import streamlit as st
        if "TIGER_DATA_URL" in st.secrets:
            return st.secrets["TIGER_DATA_URL"]
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    raise RuntimeError(
        "Falta la cadena de conexión a Tiger Data. Configúrala con UNA de estas opciones:\n"
        "  1) export DATABASE_URL='postgresql://usuario:pass@host:5432/db?sslmode=require'\n"
        "     (la misma variable que ya usa db/connection.py y main.py)\n"
        "  2) Crea un archivo .env con: DATABASE_URL=postgresql://...\n"
        "  3) Si usas Streamlit, crea .streamlit/secrets.toml con: DATABASE_URL = \"postgresql://...\""
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
    """Intenta leer también orders.estado_ciudad (evento por pedido: 'lluvia',
    'trafico', etc). Si esa columna todavía no existe en tu base (no estaba
    en el esquema original de Dev 1), cae automáticamente a la consulta sin
    ella -- no rompe el resto del motor, solo pierdes el dato del evento."""
    query_con_evento = """
        SELECT order_id, origen_lat, origen_lon, destino_lat, destino_lon,
               tarifa_base, tiempo_limite_s, estado_ciudad,
               EXTRACT(EPOCH FROM timestamp_creacion) AS ts_epoch
        FROM v_orders
        WHERE estado = 'PENDIENTE'
        ORDER BY timestamp_creacion ASC
        LIMIT %s;
    """
    query_sin_evento = """
        SELECT order_id, origen_lat, origen_lon, destino_lat, destino_lon,
               tarifa_base, tiempo_limite_s,
               EXTRACT(EPOCH FROM timestamp_creacion) AS ts_epoch
        FROM v_orders
        WHERE estado = 'PENDIENTE'
        ORDER BY timestamp_creacion ASC
        LIMIT %s;
    """
    try:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query_con_evento, (limit,))
                filas = cur.fetchall()
        tiene_evento = True
    except psycopg2.errors.UndefinedColumn:
        with get_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query_sin_evento, (limit,))
                filas = cur.fetchall()
        tiene_evento = False

    return [
        Order(
            order_id=str(f["order_id"]),
            origen=(f["origen_lat"], f["origen_lon"]),
            destino=(f["destino_lat"], f["destino_lon"]),
            tarifa_base=float(f["tarifa_base"]),
            tiempo_limite_s=int(f["tiempo_limite_s"]),
            timestamp_creacion=float(f["ts_epoch"]),
            evento=(f.get("estado_ciudad") if tiene_evento else None),
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

def registrar_decision(agente: str, entrada_log: Dict, conn=None):
    """Inserta en 'decisiones' (log de razonamiento). agente debe ser
    'BASELINE' o 'SMART' para que quede consistente con el resto del esquema.
    order_id ahora es INTEGER con FK real a orders.id (ajuste de Dev 1).

    Si se pasa 'conn' (una conexión ya abierta), la reutiliza sin abrir/
    cerrar una nueva -- así sincronizar_log_completo() puede escribir
    decenas de filas sobre UNA sola conexión en vez de una por fila."""
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
    params = (int(order_id) if order_id else None,
              agente, accion, razon, margen, json.dumps(metadata))

    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(query, params)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                cur.execute(query, params)


def registrar_batching(agente: str, entrada_log: Dict, conn=None):
    """Las entradas de 'batching' del log NO tienen un solo order_id (son un
    resumen de varios pedidos agrupados: {'accion':'batching','ordenes':[...],
    'ahorro_km':...}). Como decisiones.order_id es NOT NULL con FK, insertar
    esa entrada tal cual truena. En vez de eso, escribimos UNA fila por cada
    pedido del grupo, todas con el mismo ahorro_km en metadata, para no
    perder la trazabilidad y no violar la restricción de la tabla."""
    ordenes_del_grupo = entrada_log.get("ordenes", [])
    metadata = {k: v for k, v in entrada_log.items() if k != "ordenes"}

    query = """
        INSERT INTO decisiones (order_id, agente, accion, razon, margen_neto, metadata)
        VALUES (%s, %s, %s, %s, %s, %s);
    """

    def _insertar(cur):
        for oid in ordenes_del_grupo:
            cur.execute(query, (int(oid), agente, "batching",
                                 "agrupado_por_cercania", None, json.dumps(metadata)))

    if conn is not None:
        with conn.cursor() as cur:
            _insertar(cur)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                _insertar(cur)


def actualizar_estado_orden(order_id: str, accion: str, agente: str, conn=None):
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
    params = (nuevo_status, agente, int(order_id))

    if conn is not None:
        with conn.cursor() as cur:
            cur.execute(query, params)
    else:
        with get_connection() as c:
            with c.cursor() as cur:
                cur.execute(query, params)


## NOTA: no hay función registrar_transaccion() aquí a propósito.
## Dev 1 tiene su propio simulator.py que escucha cuando una orden pasa a
## 'ACEPTADA', simula el viaje, la marca 'COMPLETADA' e inserta en
## 'transactions'. Si nosotros también insertáramos ahí, se duplicaría la
## ganancia. Nuestro alcance termina en actualizar_estado_orden().


def sincronizar_log_completo(agente_state, agente_nombre: str, conn=None):
    """agente_nombre debe ser 'BASELINE' o 'SMART'. Vuelca el log completo
    del AgentState: escribe el razonamiento en 'decisiones' y actualiza el
    status en 'orders'. El registro en 'transactions' NO se hace aquí:
    lo dispara el simulator.py de Dev 1 cuando detecta el cambio a 'ACEPTADA'.

    Si no se pasa 'conn', abre UNA sola conexión para todo el log completo
    (en vez de una por cada fila -- esto es lo que hacía que 50 pedidos
    tardaran una eternidad). Si main.py u otro caller ya tiene una conexión
    abierta, pásala aquí para reutilizarla también."""
    def _sincronizar(c):
        for entrada in agente_state.log:
            if entrada.get("accion") == "batching":
                registrar_batching(agente_nombre, entrada, conn=c)
                continue
            registrar_decision(agente_nombre, entrada, conn=c)
            order_id = entrada.get("orden_id")
            accion = entrada.get("accion")
            if order_id and accion in ("aceptado", "rechazado"):
                actualizar_estado_orden(order_id, accion, agente_nombre, conn=c)

    if conn is not None:
        _sincronizar(conn)
    else:
        with get_connection() as c:
            _sincronizar(c)


def ejecutar_ciclo_completo(posicion_inicial: tuple, limit: int = 50, pedidos=None):
    """Corre Baseline Y Smart en paralelo sobre el MISMO lote de pedidos
    pendientes (cada uno con su propia copia de estado, para que la
    comparación de ganancias sea justa), y sincroniza el log de ambos a
    Tiger Data usando UNA SOLA conexión para todo el ciclo (mucho más
    rápido que abrir una conexión nueva por cada fila).

    Si ya leíste los pedidos tú mismo (ej. para armar el mapa en el
    frontend), pásalos en 'pedidos' para no consultarlos dos veces.

    Regresa (baseline_state, smart_state, pedidos) -- el tercer valor sirve
    para que el caller pueda mapear qué pedido exacto aceptó cada agente
    (útil para dibujar rutas DISTINTAS por agente en el mapa)."""
    from Motor_Matematico import BaselineAgent, SmartAgent

    if pedidos is None:
        pedidos = leer_pedidos_pendientes(limit=limit)

    baseline = BaselineAgent(posicion_inicial)
    orden = baseline.decidir(pedidos)
    if orden:
        baseline.ejecutar(orden)

    smart = SmartAgent(posicion_inicial)
    smart.ejecutar_turno(pedidos)

    with get_connection() as conn:
        sincronizar_log_completo(baseline.state, agente_nombre="BASELINE", conn=conn)
        sincronizar_log_completo(smart.state, agente_nombre="SMART", conn=conn)

    return baseline.state, smart.state, pedidos


# ---------------------------------------------------------------------------
# 4. DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    estado_baseline, estado_smart, pedidos = ejecutar_ciclo_completo(
        posicion_inicial=(25.6714, -100.3096))

    print(f"Pedidos evaluados por ambos agentes desde Tiger Data")
    print(f"\n=== BASELINE === ganancia: ${estado_baseline.ganancia_total:.2f}")
    for entrada in estado_baseline.log:
        print(" ", entrada)

    print(f"\n=== SMART === ganancia: ${estado_smart.ganancia_total:.2f}")
    for entrada in estado_smart.log:
        print(" ", entrada)

    print("\nDecisiones y estados sincronizados a Tiger Data (ambos agentes)")