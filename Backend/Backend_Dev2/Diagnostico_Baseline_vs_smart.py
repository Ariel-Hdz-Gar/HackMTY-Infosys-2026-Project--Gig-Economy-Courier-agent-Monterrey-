"""
Corre esto desde Backend_Dev2:  python diagnostico_baseline_vs_smart.py

Confirma si el simulator.py de Dev 1 está completando (COMPLETADA +
transactions) las órdenes de AMBOS agentes, o solo las de uno.
"""
from Tiger_Data_io import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        print("--- Conteo de orders por agente y status ---")
        cur.execute("""
            SELECT assigned_agent, status, COUNT(*)
            FROM orders
            WHERE assigned_agent IS NOT NULL
            GROUP BY assigned_agent, status
            ORDER BY assigned_agent, status;
        """)
        for fila in cur.fetchall():
            print(f"  agente={fila[0]:<10} status={fila[1]:<12} cantidad={fila[2]}")

        print("\n--- Conteo de transactions por agente ---")
        cur.execute("""
            SELECT agent_type, COUNT(*), SUM(net_profit)
            FROM transactions
            GROUP BY agent_type;
        """)
        for fila in cur.fetchall():
            print(f"  agente={fila[0]:<10} transacciones={fila[1]:<5} suma_ganancia=${fila[2]}")

        print("\n--- Órdenes ACEPTADA de Baseline que llevan MUCHO tiempo sin completarse ---")
        cur.execute("""
            SELECT id, updated_at, now() - updated_at AS tiempo_esperando
            FROM orders
            WHERE assigned_agent = 'BASELINE' AND status = 'ACEPTADA'
            ORDER BY updated_at ASC
            LIMIT 10;
        """)
        filas = cur.fetchall()
        if filas:
            for fila in filas:
                print(f"  orden #{fila[0]} lleva {fila[2]} esperando desde {fila[1]}")
        else:
            print("  (ninguna -- o todas ya se completaron, o Baseline nunca ha aceptado nada)")