import sys
import time
import threading
import logging
from dotenv import load_dotenv

# Configurar encoding para terminales en Windows
sys.stdout.reconfigure(encoding='utf-8')
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("dev1_master")

from generator import start_streaming
from simulator import start_simulation

def run_all():
    logger.info("🚀 Iniciando Motor Antigravedad de Dev 1 (Generador + Simulador de Entorno)...")
    
    # Hilo 1: Generador continuo de órdenes
    t_gen = threading.Thread(target=start_streaming, daemon=True)
    
    # Hilo 2: Simulador de ciclo de vida (Expira y Completa órdenes)
    t_sim = threading.Thread(target=start_simulation, daemon=True)
    
    t_gen.start()
    t_sim.start()
    
    logger.info("✅ Servidores de Dev 1 activos en segundo plano. Presiona Ctrl+C para detener.")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("🛑 Deteniendo servicios de Dev 1...")

if __name__ == "__main__":
    run_all()
