"""
Corre esto desde Backend_Dev2: python diagnostico_baseline_decisiones.py
"""
from Tiger_Data_io import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        print("--- Cuántas veces decidió Baseline (tabla decisiones) ---")
        cur.execute("SELECT COUNT(*) FROM decisiones WHERE agente = 'BASELINE';")
        total_baseline = cur.fetchone()[0]
        print(f"  Total de filas de BASELINE en 'decisiones': {total_baseline}")

        cur.execute("SELECT COUNT(*) FROM decisiones WHERE agente = 'SMART';")
        total_smart = cur.fetchone()[0]
        print(f"  Total de filas de SMART en 'decisiones':    {total_smart}")

        print("\n--- Últimas 5 decisiones de Baseline con fecha/hora ---")
        cur.execute("""
            SELECT order_id, accion, timestamp
            FROM decisiones
            WHERE agente = 'BASELINE'
            ORDER BY timestamp DESC
            LIMIT 5;
        """)
        filas = cur.fetchall()
        if filas:
            for fila in filas:
                print(f"  orden #{fila[0]} -> {fila[1]} @ {fila[2]}")
        else:
            print("  (ninguna fila -- confirma que Baseline solo decidió UNA vez en total)")

        print("\n--- Rango de tiempo cubierto por las decisiones de Smart (para comparar) ---")
        cur.execute("""
            SELECT MIN(timestamp), MAX(timestamp), COUNT(DISTINCT DATE_TRUNC('minute', timestamp))
            FROM decisiones WHERE agente = 'SMART';
        """)
        fila = cur.fetchone()
        print(f"  Primera decisión: {fila[0]}")
        print(f"  Última decisión:  {fila[1]}")
        print(f"  Minutos distintos con actividad: {fila[2]}")