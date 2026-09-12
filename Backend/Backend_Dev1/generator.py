import os
import time
import random
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from environment import load_or_create_graph, get_random_nodes, get_node_coords, calculate_route_distance
from db.connection import get_db_connection

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("generator")

ORDER_INTERVAL = float(os.getenv("ORDER_INTERVAL_SECONDS", "4"))
MIN_BASE_FARE = float(os.getenv("ORDER_MIN_FARE", "40.0"))
MAX_BASE_FARE = float(os.getenv("ORDER_MAX_FARE", "180.0"))
TIME_WINDOW_SEC = int(os.getenv("ORDER_TIME_WINDOW_SECONDS", "600"))


def generate_single_order(G, conn=None, event_type: str = None):
    """
    Genera un pedido simulado eligiendo nodos reales de la red vial de Monterrey
    e insertándolo en la tabla 'orders' de Tiger Data.
    Soporta tipos de evento: 'normal', 'clima', 'trafico'.
    """
    nodes = get_random_nodes(G, n=2)
    orig_node, dest_node = nodes[0], nodes[1]
    
    orig_lat, orig_lon = get_node_coords(G, orig_node)
    dest_lat, dest_lon = get_node_coords(G, dest_node)

    # Si no se especifica evento, 80% normal, 10% clima, 10% trafico
    if not event_type:
        event_type = random.choices(["normal", "clima", "trafico"], weights=[0.8, 0.1, 0.1])[0]

    # Calcular distancia real para sugerir tarifa realista
    distance_meters = calculate_route_distance(G, orig_node, dest_node, weight="length")
    
    if distance_meters == float("inf") or distance_meters <= 0:
        # Fallback si no hay ruta directa conectada
        calculated_fare = round(random.uniform(MIN_BASE_FARE, MAX_BASE_FARE), 2)
    else:
        # Tarifa base: $30 base + $12 por cada km
        km = distance_meters / 1000.0
        calculated_fare = round(max(MIN_BASE_FARE, min(MAX_BASE_FARE, 30.0 + (km * 12.0))), 2)

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=TIME_WINDOW_SEC)

    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO orders (
                    origin_lat, origin_lon, dest_lat, dest_lon,
                    origin_node_id, dest_node_id,
                    base_fare, time_window_seconds, expires_at, status, event_type
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
                """,
                (
                    orig_lat, orig_lon, dest_lat, dest_lon,
                    orig_node, dest_node,
                    calculated_fare, TIME_WINDOW_SEC, expires_at, "PENDIENTE", event_type
                )
            )
            order_id = cur.fetchone()[0]
        conn.commit()
        
        dist_km_str = f"{distance_meters/1000.0:.2f} km" if distance_meters != float("inf") else "N/A"
        logger.info(
            f" [Orden #{order_id} Creada] Evento: {event_type} | Tarifa: ${calculated_fare} MXN | Distancia: {dist_km_str} | "
            f"Origen: ({orig_lat:.4f}, {orig_lon:.4f}) -> Destino: ({dest_lat:.4f}, {dest_lon:.4f})"
        )
        return order_id
    except Exception as e:
        conn.rollback()
        logger.error(f"Error al insertar orden en Tiger Data: {e}")
        return None
    finally:
        if should_close:
            conn.close()


def start_streaming(interval_seconds: float = ORDER_INTERVAL, max_orders: int = None):
    """
    Inicia el bucle de streaming continuo de pedidos simulados en Monterrey.
    """
    logger.info("Cargando grafo vial de Monterrey...")
    G = load_or_create_graph()
    logger.info(f"Iniciando streaming de órdenes cada {interval_seconds}s hacia Tiger Data...")

    count = 0
    try:
        while True:
            generate_single_order(G)
            count += 1
            if max_orders and count >= max_orders:
                logger.info(f"Límite de {max_orders} órdenes alcanzado.")
                break
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        logger.info("Streaming detenido manualmente por el usuario.")


if __name__ == "__main__":
    start_streaming()
