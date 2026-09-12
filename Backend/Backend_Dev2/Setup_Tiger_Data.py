"""
CourierAI - Seed de datos de prueba para Tiger Data
------------------------------------------------------
Las tablas YA las creó Dev 1 (ver SCRIPT_SQL.txt) -- este script NO las
vuelve a crear, solo inserta pedidos de prueba con estado PENDIENTE para
que puedas probar tiger_data_io.py de punta a punta.

Uso:
  python3 setup_tiger_data.py            -> inserta 4 pedidos de prueba
  python3 setup_tiger_data.py --limpiar  -> borra pedidos y sus decisiones/transacciones
"""

import sys
from Tiger_Data_io import get_connection

PEDIDOS_PRUEBA = [
    # (origin_lat, origin_lon, dest_lat, dest_lon, base_fare, time_window_seconds)
    (25.671, -100.309, 25.665, -100.300, 65, 1800),
    (25.672, -100.310, 25.667, -100.301, 40, 1800),
    (25.669, -100.308, 25.700, -100.350, 30, 1200),  # margen probablemente negativo
    (25.673, -100.311, 25.666, -100.302, 55, 1800),
]


def sembrar_pedidos():
    with get_connection() as conn:
        with conn.cursor() as cur:
            for (olat, olon, dlat, dlon, tarifa, ventana) in PEDIDOS_PRUEBA:
                cur.execute(
                    """INSERT INTO orders
                       (origin_lat, origin_lon, dest_lat, dest_lon,
                        base_fare, time_window_seconds, status)
                       VALUES (%s, %s, %s, %s, %s, %s, 'PENDIENTE')""",
                    (olat, olon, dlat, dlon, tarifa, ventana),
                )
    print(f"✅ {len(PEDIDOS_PRUEBA)} pedidos de prueba insertados con status='PENDIENTE'.")


def limpiar():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM transactions;")
            cur.execute("DELETE FROM decisiones;")
            cur.execute("DELETE FROM driver_logs;")
            cur.execute("DELETE FROM orders;")
    print("🗑️  Pedidos, decisiones, transacciones y logs de repartidores eliminados.")


if __name__ == "__main__":
    if "--limpiar" in sys.argv:
        limpiar()
    else:
        sembrar_pedidos()