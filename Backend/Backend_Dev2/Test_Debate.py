"""
Prueba manual de debate_rutas.py:
  - 3 rutas candidatas (no solo 2) para confirmar que escala.
  - Un generador_texto de prueba que SÍ varía según los datos, en vez del
    stub genérico, para verificar visualmente que cada ruta recibe un
    argumento distinto y que el mediador usa las métricas reales.
Corre con: python3 test_debate.py
"""
import uuid
from Backend.Backend_Dev2.Motor_Matematico import Order
from Backend.Backend_Dev2.Debate_Rutas import generar_opciones_ruta, debatir_rutas


def generador_texto_prueba(prompt: str) -> str:
    """Simula lo que haría Gemini, pero reacciona a los números del prompt
    en vez de regresar texto fijo. Útil para probar sin gastar API real."""
    if "mediador" in prompt.lower() or "Decide cuál ruta" in prompt:
        return "[MEDIADOR] Analizando métricas de todas las rutas..."
    # extrae el nombre de la ruta que se está defendiendo
    primera_linea = prompt.split("\n")[0]
    return f"[ARGUMENTO] {primera_linea} Defiendo esta ruta con base en mis métricas."


posicion_inicial = (25.6714, -100.3096)
pedidos_mock = [
    Order(str(uuid.uuid4())[:8], (25.671, -100.309), (25.665, -100.300), 65, 1800),
    Order(str(uuid.uuid4())[:8], (25.672, -100.310), (25.667, -100.301), 40, 1800),
    Order(str(uuid.uuid4())[:8], (25.673, -100.311), (25.700, -100.350), 90, 2400),
]

# k=3 para forzar la tercera estrategia (ruta_rentable)
opciones = generar_opciones_ruta(posicion_inicial, pedidos_mock, k=3)
print(f"Se generaron {len(opciones)} rutas candidatas:\n")
for o in opciones:
    print(f"  {o.id}: {o.descripcion} | {o.distancia_km}km | "
          f"ganancia=${o.ganancia_neta} | riesgo={o.riesgo}")

resultado = debatir_rutas(opciones, generador_texto=generador_texto_prueba)

print("\n--- Resultado del debate ---")
for op in resultado["opciones"]:
    print(f"\n[{op['id']}]")
    print("  Argumento:", op["argumento"])
print("\nVeredicto:", resultado["veredicto_mediador"])