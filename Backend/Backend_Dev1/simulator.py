import os
import sys
import time
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv

from db.connection import get_db_connection

# Configurar encoding para la terminal de Windows
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("simulator")

TICK_INTERVAL = 5.0  # Segundos entre cada ciclo de simulación
SIMULATED_DELIVERY_TIME_SEC = 20.0 # Segundos que toma "entregar" una orden en esta simulación

def simulate_tick():
    """
    Simula el paso del tiempo en el entorno:
    1. Las órdenes PENDIENTES expiradas pasan a EXPIRADA.
    2. Las órdenes ACEPTADAS que ya pasaron su tiempo de entrega simulado pasan a COMPLETADA, 
       generando una transacción.
    """
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            now = datetime.now(timezone.utc)
            
            # 1. Expirar órdenes
            cur.execute(
                """
                UPDATE orders 
                SET status = 'EXPIRADA', updated_at = %s
                WHERE status = 'PENDIENTE' AND expires_at < %s
                RETURNING id;
                """,
                (now, now)
            )
            expired = cur.fetchall()
            for row in expired:
                logger.info(f"⏳ Orden #{row[0]} ha expirado por falta de agente.")
                
            # 2. Completar órdenes aceptadas
            # Buscamos órdenes aceptadas hace más de SIMULATED_DELIVERY_TIME_SEC
            cur.execute(
                """
                SELECT id, base_fare, assigned_agent 
                FROM orders 
                WHERE status = 'ACEPTADA' 
                  AND EXTRACT(EPOCH FROM (%s - updated_at)) >= %s;
                """,
                (now, SIMULATED_DELIVERY_TIME_SEC)
            )
            to_complete = cur.fetchall()
            
            for order_id, base_fare, agent_type in to_complete:
                if not agent_type:
                    agent_type = 'BASELINE' # Fallback
                
                # Mock de costo operacional aleatorio/basado en tarifa
                operational_cost = round(float(base_fare) * 0.4, 2) # 40% de costo
                net_profit = round(float(base_fare) - operational_cost, 2)
                
                # Actualizar orden
                cur.execute(
                    """
                    UPDATE orders 
                    SET status = 'COMPLETADA', updated_at = %s 
                    WHERE id = %s
                    """,
                    (now, order_id)
                )
                
                # Insertar en transactions
                cur.execute(
                    """
                    INSERT INTO transactions (order_id, agent_type, gross_fare, operational_cost, net_profit)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (order_id, agent_type, base_fare, operational_cost, net_profit)
                )
                
                logger.info(f"✅ Orden #{order_id} COMPLETADA por {agent_type}. Ganancia neta: ${net_profit}")
                
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Error en tick de simulación: {e}")
    finally:
        conn.close()

def start_simulation():
    logger.info("🚀 Iniciando loop de simulación del entorno (Dev 1)...")
    try:
        while True:
            simulate_tick()
            time.sleep(TICK_INTERVAL)
    except KeyboardInterrupt:
        logger.info("🛑 Simulación detenida manualmente.")

if __name__ == "__main__":
    start_simulation()
