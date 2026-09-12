"""
Prueba de punta a punta: motor de Dev 2 -> microservicio de Dev 3 (Gemini).

REQUISITOS antes de correr esto:
  1. Dev 3 debe tener su servidor corriendo en otra terminal:
       uvicorn main:app --port 8000
     (desde la carpeta donde esté su main.py de FastAPI)
  2. Dev 3 debe tener GEMINI_API_KEY configurada en SU .env (para que
     genai.Client() funcione del lado de él -- eso no es algo que tú
     puedas arreglar desde aquí).
  3. Idealmente, generator.py de Dev 1 corriendo para tener pedidos reales.

Uso: python3 prueba_gemini_dev3.py
"""
import requests

from Tiger_Data_io import leer_pedidos_pendientes, ejecutar_ciclo_completo
from Gemini_Bridge import explicar_evento_con_dev3, GEMINI_SERVICE_URL

# --- Paso 1: ¿está vivo el servidor de Dev 3? ---
url_base = GEMINI_SERVICE_URL.rsplit("/evaluar-rutas", 1)[0] or "http://127.0.0.1:8000"
print(f"Paso 1: probando conexión a {url_base} ...")
try:
    resp = requests.get(url_base, timeout=5)
    print(f"  ✅ Servidor de Dev 3 responde: {resp.json()}")
except requests.exceptions.ConnectionError:
    print(f"  ❌ No hay nadie escuchando en {url_base}.")
    print("     Pídele a Dev 3 que corra: uvicorn main:app --port 8000")
    print("     (Deteniendo la prueba aquí, no tiene caso seguir.)")
    raise SystemExit(1)
except Exception as e:
    print(f"  ⚠️  El servidor respondió pero con un error: {e}")

# --- Paso 2: correr el motor real sobre pedidos reales de Tiger Data ---
print("\nPaso 2: corriendo Baseline y Smart sobre pedidos reales...")
pedidos = leer_pedidos_pendientes(limit=50)
print(f"  Pedidos PENDIENTE leídos: {len(pedidos)}")

if not pedidos:
    print("  ⚠️  No hay pedidos pendientes -- corre generator.py primero.")
    raise SystemExit(1)

baseline_state, smart_state = ejecutar_ciclo_completo(posicion_inicial=(25.6714, -100.3096))
print(f"  BASELINE: ${baseline_state.ganancia_total:.2f} | SMART: ${smart_state.ganancia_total:.2f}")

# --- Paso 3: llamar de verdad al endpoint de Dev 3 con esos datos ---
print("\nPaso 3: pidiéndole a Gemini (vía Dev 3) que explique la decisión...")
resultado = explicar_evento_con_dev3(
    "Tráfico intenso en Avenida Constitución",
    pedidos, baseline_state, smart_state,
)

print("\n--- Resultado ---")
print("Agente ganador:", resultado.get("agente_ganador"))
print("Explicación:   ", resultado.get("explicacion_gemini"))

if "Sin conexión" in str(resultado.get("explicacion_gemini", "")) or \
   "Error conectando" in str(resultado.get("explicacion_gemini", "")):
    print("\n⚠️  La llamada falló o cayó al respaldo -- revisa el mensaje de arriba.")
else:
    print("\n✅ ¡Funciona! Esa explicación la generó Gemini de verdad, vía el servicio de Dev 3.")