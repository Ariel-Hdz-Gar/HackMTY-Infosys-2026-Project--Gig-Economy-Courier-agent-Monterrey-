"""
Corre esto desde Backend_Dev2: python verificar_ganancia_baseline.py
"""
from Tiger_Data_io import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT SUM(margen_neto), COUNT(*)
            FROM decisiones
            WHERE agente = 'BASELINE' AND accion = 'aceptado'
        """)
        suma_total, cantidad_total = cur.fetchone()
        print(f"Baseline aceptó en total: {cantidad_total} pedidos, suma bruta ${suma_total}")

        cur.execute("""
            SELECT SUM(d1.margen_neto), COUNT(*)
            FROM decisiones d1
            WHERE d1.agente = 'BASELINE' AND d1.accion = 'aceptado'
              AND NOT EXISTS (
                  SELECT 1 FROM decisiones d2
                  WHERE d2.order_id = d1.order_id
                    AND d2.agente = 'SMART' AND d2.accion = 'aceptado'
              )
        """)
        suma_exclusiva, cantidad_exclusiva = cur.fetchone()
        print(f"Baseline se quedó (Smart NO lo quería): {cantidad_exclusiva} pedidos, suma ${suma_exclusiva}")
        print(f"Baseline 'perdió' contra Smart: {cantidad_total - cantidad_exclusiva} pedidos")