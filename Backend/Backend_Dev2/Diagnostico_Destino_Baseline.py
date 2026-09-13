"""
Corre esto desde Backend_Dev2: python diagnostico_destino_baseline.py
"""
from Tiger_Data_io import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        print("--- Destino final de TODAS las órdenes que Baseline aceptó alguna vez ---")
        cur.execute("""
            SELECT o.status, COUNT(*)
            FROM orders o
            WHERE o.id IN (
                SELECT DISTINCT order_id FROM decisiones
                WHERE agente = 'BASELINE' AND accion = 'aceptado'
            )
            GROUP BY o.status
            ORDER BY COUNT(*) DESC;
        """)
        for fila in cur.fetchall():
            print(f"  status={fila[0]:<12} cantidad={fila[1]}")

        print("\n--- Si hay EXPIRADA: cuánto tiempo pasó entre aceptarla y expirar ---")
        cur.execute("""
            SELECT o.id, o.time_window_seconds, o.created_at, o.updated_at,
                   EXTRACT(EPOCH FROM (o.updated_at - o.created_at)) AS segundos_reales
            FROM orders o
            WHERE o.status = 'EXPIRADA'
              AND o.id IN (
                  SELECT DISTINCT order_id FROM decisiones
                  WHERE agente = 'BASELINE' AND accion = 'aceptado'
              )
            ORDER BY o.updated_at DESC
            LIMIT 5;
        """)
        filas = cur.fetchall()
        if filas:
            for fila in filas:
                print(f"  orden #{fila[0]}: ventana={fila[1]}s, tardó {fila[4]:.0f}s en total "
                      f"(creada {fila[2]}, expiró/actualizó {fila[3]})")
        else:
            print("  (ninguna con status EXPIRADA -- revisa qué otro status salió arriba)")