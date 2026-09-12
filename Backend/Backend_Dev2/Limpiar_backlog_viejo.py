"""
Corre esto UNA vez desde Backend_Dev2 para limpiar el backlog de pedidos
PENDIENTE que ya están viejos/vencidos (antes de que ORDER_TIME_WINDOW_SECONDS
más grande empiece a generar pedidos nuevos con plazo razonable).

Uso:
  python3 limpiar_backlog_viejo.py
"""
from Tiger_Data_io import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE orders
            SET status = 'EXPIRADA', updated_at = now()
            WHERE status = 'PENDIENTE';
            """
        )
        print(f"{cur.rowcount} pedidos viejos marcados como EXPIRADA.")

print("Listo. La próxima vez que corras prueba_tiger_real.py, solo vas a ver pedidos frescos.")