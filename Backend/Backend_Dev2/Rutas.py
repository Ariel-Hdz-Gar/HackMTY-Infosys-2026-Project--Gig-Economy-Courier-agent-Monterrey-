"""
CourierAI - Generación de rutas candidatas + Debate multi-IA (Dev 2 + Dev 3)
-----------------------------------------------------------------------------
Dev 2 (tú) es dueño de: generar_opciones_ruta() -> produce k RouteOption con
métricas cuantificadas y objetivas (distancia, tiempo, riesgo, ganancia).

Dev 3 es dueño de: la función call_gemini() (implementación real de la API)
y de afinar los prompts. Aquí dejo el orquestador ya armado para que solo
conecte su cliente de Gemini en el punto marcado.
"""

from dataclasses import dataclass, field
from typing import List, Callable, Optional

from Motor_Matematico import (
    Order, distancia_km, margen_neto, multiplicador_para,
    COSTO_POR_KM, COSTO_POR_MINUTO, VELOCIDAD_KMH,
)


# ---------------------------------------------------------------------------
# 1. CANDIDATAS DE RUTA (dominio de Dev 2)
# ---------------------------------------------------------------------------

@dataclass
class RouteOption:
    id: str
    puntos: List[tuple]          # secuencia de coordenadas de la ruta
    distancia_km: float
    tiempo_min: float
    riesgo: float                # 0-1, basado en zonas penalizadas activas
    ganancia_neta: float
    descripcion: str             # resumen legible de la estrategia
    argumento: Optional[str] = field(default=None)  # lo llena la IA debatiente


def _construir_metrica(puntos: List[tuple], id_: str, descripcion: str,
                        pedidos: List[Order]) -> RouteOption:
    dist = sum(distancia_km(puntos[i], puntos[i + 1]) for i in range(len(puntos) - 1))
    tiempo_min = (dist / VELOCIDAD_KMH) * 60

    riesgos = [multiplicador_para(o) for o in pedidos]
    riesgo = max(0.0, (max(riesgos) - 1.0)) if riesgos else 0.0  # 0 = normal

    ganancia = sum(margen_neto(o, puntos[0], multiplicador_para(o)) for o in pedidos)

    return RouteOption(id=id_, puntos=puntos, distancia_km=round(dist, 2),
                        tiempo_min=round(tiempo_min, 1), riesgo=round(riesgo, 2),
                        ganancia_neta=round(ganancia, 2), descripcion=descripcion)


def generar_opciones_ruta(posicion_agente: tuple, pedidos: List[Order],
                            k: int = 2) -> List[RouteOption]:
    """
    Genera k rutas candidatas con estrategias distintas para que cada una
    tenga argumentos reales y diferenciados (no solo variantes triviales):
      - Opción A: orden que minimiza distancia total (greedy nearest-neighbor)
      - Opción B: orden que minimiza riesgo (evita zonas penalizadas primero)
      - Opción C (si k>=3): orden que maximiza ganancia acumulada temprana
    """
    opciones = []

    # --- A) Nearest-neighbor por distancia ---
    restantes = pedidos.copy()
    ruta = [posicion_agente]
    pos = posicion_agente
    orden_a = []
    while restantes:
        siguiente = min(restantes, key=lambda o: distancia_km(pos, o.destino))
        ruta.append(siguiente.destino)
        pos = siguiente.destino
        orden_a.append(siguiente)
        restantes.remove(siguiente)
    opciones.append(_construir_metrica(
        ruta, "ruta_corta", "Minimiza la distancia total recorrida", orden_a))

    # --- B) Prioriza evitar pedidos en zonas penalizadas ---
    ordenados_b = sorted(pedidos, key=lambda o: multiplicador_para(o))
    ruta_b = [posicion_agente] + [o.destino for o in ordenados_b]
    opciones.append(_construir_metrica(
        ruta_b, "ruta_segura", "Prioriza zonas sin penalización (evita riesgo)",
        ordenados_b))

    # --- C) Prioriza ganancia por pedido, de mayor a menor ---
    if k >= 3:
        ordenados_c = sorted(
            pedidos,
            key=lambda o: margen_neto(o, posicion_agente, multiplicador_para(o)),
            reverse=True,
        )
        ruta_c = [posicion_agente] + [o.destino for o in ordenados_c]
        opciones.append(_construir_metrica(
            ruta_c, "ruta_rentable", "Prioriza los pedidos de mayor margen primero",
            ordenados_c))

    return opciones[:k]


# ---------------------------------------------------------------------------
# 2. DEBATE MULTI-IA (Dev 3 conecta Gemini aquí)
# ---------------------------------------------------------------------------

# >>> Dev 3: reemplaza esta función por la llamada real a la API de Gemini <<<
def call_gemini(prompt: str) -> str:
    """STUB. Sustituir por la llamada real, ej:
        model = genai.GenerativeModel('gemini-1.5-flash')
        return model.generate_content(prompt).text
    """
    return f"[Respuesta simulada de Gemini para prompt de {len(prompt)} caracteres]"


def prompt_defensor(opcion: RouteOption, otras: List[RouteOption]) -> str:
    comparacion = "\n".join(
        f"- {o.id}: distancia={o.distancia_km}km, tiempo={o.tiempo_min}min, "
        f"riesgo={o.riesgo}, ganancia=${o.ganancia_neta}"
        for o in otras
    )
    return (
        f"Eres un agente repartidor defendiendo la ruta '{opcion.id}'.\n"
        f"Tus métricas: distancia={opcion.distancia_km}km, "
        f"tiempo={opcion.tiempo_min}min, riesgo={opcion.riesgo}, "
        f"ganancia=${opcion.ganancia_neta}.\n"
        f"Rutas alternativas:\n{comparacion}\n"
        f"En máximo 3 líneas, argumenta por qué tu ruta es la mejor opción "
        f"para este turno."
    )


def prompt_mediador(opciones: List[RouteOption]) -> str:
    resumen = "\n\n".join(
        f"Ruta {o.id} ({o.descripcion}):\n"
        f"  Métricas: distancia={o.distancia_km}km, tiempo={o.tiempo_min}min, "
        f"riesgo={o.riesgo}, ganancia=${o.ganancia_neta}\n"
        f"  Argumento: {o.argumento}"
        for o in opciones
    )
    return (
        f"Eres el mediador imparcial del sistema. Estas son las rutas "
        f"propuestas, sus métricas objetivas y el argumento de cada agente:\n\n"
        f"{resumen}\n\n"
        f"Decide cuál ruta es la mejor opción para el repartidor. Responde "
        f"con el id de la ruta ganadora y una justificación breve (máx 3 "
        f"líneas) basada en los datos, no solo en los argumentos."
    )


def debatir_rutas(opciones: List[RouteOption],
                   generador_texto: Callable[[str], str] = call_gemini) -> dict:
    """
    Orquesta el debate:
      1) Cada ruta obtiene un argumento de su agente defensor.
      2) El mediador recibe todos los argumentos + métricas y decide.
    Funciona igual para 2 opciones o para N (todas contra todas).
    """
    for opcion in opciones:
        otras = [o for o in opciones if o.id != opcion.id]
        opcion.argumento = generador_texto(prompt_defensor(opcion, otras))

    veredicto = generador_texto(prompt_mediador(opciones))

    return {
        "opciones": [
            {"id": o.id, "descripcion": o.descripcion, "argumento": o.argumento,
             "metricas": {"distancia_km": o.distancia_km, "tiempo_min": o.tiempo_min,
                          "riesgo": o.riesgo, "ganancia_neta": o.ganancia_neta}}
            for o in opciones
        ],
        "veredicto_mediador": veredicto,
    }


# ---------------------------------------------------------------------------
# 3. DEMO LOCAL
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uuid

    posicion_inicial = (25.6714, -100.3096)
    pedidos_mock = [
        Order(str(uuid.uuid4())[:8], (25.671, -100.309), (25.665, -100.300), 65, 1800),
        Order(str(uuid.uuid4())[:8], (25.672, -100.310), (25.667, -100.301), 40, 1800),
        Order(str(uuid.uuid4())[:8], (25.673, -100.311), (25.700, -100.350), 55, 1800),
    ]

    opciones = generar_opciones_ruta(posicion_inicial, pedidos_mock, k=2)
    for o in opciones:
        print(o.id, "->", o.descripcion, "|", o.distancia_km, "km",
              "| ganancia:", o.ganancia_neta)

    print("\n--- Debate (usando stub de Gemini) ---")
    resultado = debatir_rutas(opciones)
    for op in resultado["opciones"]:
        print(f"\n[{op['id']}] {op['descripcion']}")
        print("  Métricas:", op["metricas"])
        print("  Argumento:", op["argumento"])
    print("\nVeredicto del mediador:", resultado["veredicto_mediador"])