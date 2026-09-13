"""
CourierAI - Puente con Gemini (Dev 2 <-> Dev 3)
---------------------------------------------------
Este es el ÚNICO lugar donde se llama a la API de Gemini. Tanto el debate
de rutas (debate_rutas.py) como la explicación del evento disruptor
(el flujo principal que pide el documento) pasan por aquí, para que
Dev 3 solo tenga que implementar UNA función real, no varias.

>>> DEV 3: tu trabajo es reemplazar SOLO call_gemini() por la llamada real
>>> a la API. Todo lo demás (los prompts, el armado del contexto) ya está
>>> hecho del lado de Dev 2 y no debería necesitar cambios.
"""

import logging
import requests
from typing import Callable, Dict, List

logger = logging.getLogger("gemini_bridge")

# URL del microservicio FastAPI de Dev 3. Si él lo despliega en otro puerto
# o en un servidor distinto de localhost, actualiza esto (o mejor, pásalo
# por variable de entorno -- ver GEMINI_SERVICE_URL más abajo).
import os
GEMINI_SERVICE_URL = os.environ.get("GEMINI_SERVICE_URL", "http://localhost:8000/evaluar-rutas")


# ---------------------------------------------------------------------------
# 1. PUNTO ÚNICO DE CONTACTO CON LA API (ahora vía el microservicio de Dev 3)
# ---------------------------------------------------------------------------

def call_gemini(prompt: str) -> str:
    """Llama al microservicio FastAPI de Dev 3 (Opción A: monolito local ->
    microservicio). Dev 3 corre su servidor con:
        uvicorn main:app --port 8000
    y este archivo le manda el prompt ya armado como 'evento_contexto'.

    NOTA: opcion_baseline / opcion_smart van vacías/en cero porque nuestras
    funciones (prompt_defensor_ruta, prompt_mediador_rutas,
    explicar_evento_disruptor) ya comprimen todo el contexto relevante
    dentro del texto de 'prompt'. Si el endpoint de Dev 3 necesita esos
    campos poblados de verdad (no solo el texto), hay que rediseñar la
    llamada para pasar datos estructurados en vez de un string plano --
    confírmalo con él antes de confiar en la calidad de la respuesta."""
    try:
        response = requests.post(
            GEMINI_SERVICE_URL,
            json={
                "evento_contexto": prompt,
                "opcion_baseline": {
                    "agente": "Baseline",
                    "ruta_nodos": [],
                    "tiempo_est_min": 0,
                    "ganancia_neta_mxn": 0,
                    "argumento_agente": ""
                },
                "opcion_smart": {
                    "agente": "Smart",
                    "ruta_nodos": [],
                    "tiempo_est_min": 0,
                    "ganancia_neta_mxn": 0,
                    "argumento_agente": ""
                } 
            },
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["explicacion_gemini"]
    except requests.exceptions.ConnectionError:
        logger.warning(
            f"No se pudo conectar al microservicio de Dev 3 en {GEMINI_SERVICE_URL}. "
            f"¿Está corriendo 'uvicorn main:app --port 8000'? Usando texto simulado."
        )
        return f"[Sin conexión al servicio de Gemini - prompt de {len(prompt)} caracteres]"
    except Exception as e:
        logger.warning(f"Error llamando al microservicio de Dev 3: {e}")
        return f"[Error conectando a FastAPI: {e}]"


# ---------------------------------------------------------------------------
# 2. DEBATE DE RUTAS (usado por debate_rutas.py)
# ---------------------------------------------------------------------------

def prompt_defensor_ruta(opcion, otras: List) -> str:
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


def prompt_mediador_rutas(opciones: List) -> str:
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


# ---------------------------------------------------------------------------
# 3. EXPLICACIÓN DEL EVENTO DISRUPTOR (flujo principal del documento)
#    "El Agente Inteligente recalcula su ruta y envía el nuevo contexto
#     geográfico a la API de Gemini." -> esto es exactamente eso.
# ---------------------------------------------------------------------------

def resumen_agente(agente_state) -> Dict:
    """Convierte un AgentState de motor_matematico.py en un resumen chico
    para no mandarle a Gemini el log completo, solo lo relevante."""
    aceptados = [e for e in agente_state.log if e.get("accion") == "aceptado"]
    rechazados = [e for e in agente_state.log if e.get("accion") == "rechazado"]
    return {
        "ganancia": round(agente_state.ganancia_total, 2),
        "pedidos_aceptados": len(aceptados),
        "pedidos_rechazados": len(rechazados),
        "razones_rechazo": list({e.get("razon") for e in rechazados if e.get("razon")}),
    }


def construir_propuesta_ruta(nombre_agente: str, agente_state, pedidos_por_id: Dict[str, object]) -> Dict:
    """Arma un dict con la forma EXACTA que espera PropuestaRuta de Dev 3
    (schemas.py): agente, ruta_nodos, tiempo_est_min, ganancia_neta_mxn,
    argumento_agente. pedidos_por_id: {order_id: Order} -- para recuperar
    origen/destino reales de cada pedido aceptado y calcular el tiempo."""
    from Motor_Matematico import distancia_km, VELOCIDAD_KMH

    aceptados = [e for e in agente_state.log if e.get("accion") == "aceptado"]
    ruta_nodos: List[str] = []
    tiempo_total_min = 0.0

    for entrada in aceptados:
        oid = entrada.get("orden_id")
        orden = pedidos_por_id.get(oid)
        if orden:
            ruta_nodos.append(
                f"Pedido #{oid}: ({orden.origen[0]:.4f},{orden.origen[1]:.4f}) "
                f"-> ({orden.destino[0]:.4f},{orden.destino[1]:.4f})"
            )
            dist_km = distancia_km(orden.origen, orden.destino)
            tiempo_total_min += (dist_km / VELOCIDAD_KMH) * 60
        else:
            ruta_nodos.append(f"Pedido #{oid}")

    if not ruta_nodos:
        ruta_nodos = ["Sin pedidos aceptados en este ciclo"]

    if nombre_agente.upper() == "SMART":
        argumento = (
            f"Evaluó {len(agente_state.log)} pedidos con OR-Tools: aceptó "
            f"{len(aceptados)} por margen neto positivo y tiempo alcanzable, "
            f"descartando el resto por rentabilidad o plazo."
        )
    else:
        argumento = (
            f"Aceptó {len(aceptados)} pedido(s) por orden de llegada (FIFO), "
            f"sin evaluar rentabilidad ni tiempo de entrega."
        )

    return {
        "agente": nombre_agente.capitalize(),
        "ruta_nodos": ruta_nodos,
        "tiempo_est_min": round(tiempo_total_min),
        "ganancia_neta_mxn": round(agente_state.ganancia_total, 2),
        "argumento_agente": argumento,
    }


def evaluar_rutas_con_dev3(evento_contexto: str, propuesta_baseline: Dict,
                            propuesta_smart: Dict) -> Dict:
    """Llama al endpoint REAL de Dev 3 (/evaluar-rutas) con el schema exacto
    que espera SolicitudMediacion. Regresa {'agente_ganador':..., 'explicacion_gemini':...}
    (RespuestaMediacion), o un respaldo simulado si su servicio no responde."""
    try:
        response = requests.post(
            GEMINI_SERVICE_URL,
            json={
                "evento_contexto": evento_contexto,
                "opcion_baseline": propuesta_baseline,
                "opcion_smart": propuesta_smart,
            },
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        logger.warning(
            f"No se pudo conectar al microservicio de Dev 3 en {GEMINI_SERVICE_URL}. "
            f"¿Está corriendo 'uvicorn main:app --port 8000'?"
        )
        return {
            "agente_ganador": propuesta_smart.get("agente", "Smart"),
            "explicacion_gemini": "[Sin conexión al servicio de Gemini de Dev 3]",
        }
    except Exception as e:
        logger.warning(f"Error llamando al microservicio de Dev 3: {e}")
        return {"agente_ganador": propuesta_smart.get("agente", "Smart"),
                "explicacion_gemini": f"[Error conectando a FastAPI: {e}]"}


def prompt_evento_disruptor(evento_info: Dict, resumen_antes: Dict, resumen_despues: Dict) -> str:
    return (
        f"Eres el sistema de explicabilidad de un repartidor autónomo en "
        f"Monterrey. Se acaba de activar un evento disruptor:\n"
        f"  Tipo: {evento_info['tipo']}\n"
        f"  Zona afectada (lat, lon): {evento_info['zona']}\n"
        f"  Radio: {evento_info['radio_km']} km\n"
        f"  Multiplicador de costo aplicado: {evento_info['multiplicador']}x\n\n"
        f"Estrategia ANTES del evento: ganancia=${resumen_antes['ganancia']}, "
        f"{resumen_antes['pedidos_aceptados']} pedidos aceptados, "
        f"{resumen_antes['pedidos_rechazados']} rechazados.\n"
        f"Estrategia DESPUÉS del evento: ganancia=${resumen_despues['ganancia']}, "
        f"{resumen_despues['pedidos_aceptados']} pedidos aceptados, "
        f"{resumen_despues['pedidos_rechazados']} rechazados "
        f"(razones: {', '.join(resumen_despues['razones_rechazo']) or 'ninguna'}).\n\n"
        f"En máximo 3 líneas y en lenguaje natural, explica para el jurado por "
        f"qué el agente cambió su estrategia a raíz de este evento. Sé "
        f"específico sobre la causa geográfica (ej. 'Rechacé por tráfico en "
        f"Constitución')."
    )


def explicar_evento_disruptor(evento_info: Dict, agente_antes, agente_despues,
                                generador_texto: Callable[[str], str] = call_gemini) -> str:
    """Versión simple (texto plano, para casos donde no tienes los pedidos
    originales a la mano). Usa el stub/adaptador genérico call_gemini().
    Para conectar con el endpoint REAL de Dev 3, usa explicar_evento_con_dev3()
    en su lugar -- esa sí manda el JSON estructurado que su servicio espera."""
    resumen_antes = resumen_agente(agente_antes)
    resumen_despues = resumen_agente(agente_despues)
    prompt = prompt_evento_disruptor(evento_info, resumen_antes, resumen_despues)
    return generador_texto(prompt)


def explicar_evento_con_dev3(evento_texto: str, pedidos: List, baseline_state,
                               smart_state) -> Dict:
    """Punto de entrada recomendado: arma el JSON con la forma exacta que
    espera el microservicio real de Dev 3 y lo llama.

    evento_texto: descripción libre del evento, ej. "Lluvia intensa en zona
                  de Contry" -- esto llena evento_contexto.
    pedidos: la lista de Order que se le pasó a ambos agentes (para poder
             reconstruir origen/destino de cada pedido aceptado).
    baseline_state / smart_state: AgentState de cada agente tras correr.

    Regresa {'agente_ganador':..., 'explicacion_gemini':...} listo para
    mostrar en pantalla."""
    pedidos_por_id = {p.order_id: p for p in pedidos}
    propuesta_baseline = construir_propuesta_ruta("Baseline", baseline_state, pedidos_por_id)
    propuesta_smart = construir_propuesta_ruta("Smart", smart_state, pedidos_por_id)
    return evaluar_rutas_con_dev3(evento_texto, propuesta_baseline, propuesta_smart)


# ---------------------------------------------------------------------------
# 4. DEMO
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uuid
    from Motor_Matematico import Order, SmartAgent, activar_evento, desactivar_eventos

    posicion_inicial = (25.6714, -100.3096)
    pedidos = [
        Order(str(uuid.uuid4())[:8], (25.671, -100.309), (25.665, -100.300), 65, 1800),
        Order(str(uuid.uuid4())[:8], (25.672, -100.310), (25.667, -100.301), 40, 1800),
        Order(str(uuid.uuid4())[:8], (25.673, -100.311), (25.666, -100.302), 55, 1800),
    ]

    desactivar_eventos()
    agente_antes = SmartAgent(posicion_inicial)
    agente_antes.ejecutar_turno(pedidos)
    print("Antes del evento:", resumen_agente(agente_antes.state))

    evento_info = activar_evento((25.666, -100.301), radio_km=1.0, tipo="lluvia")

    agente_despues = SmartAgent(posicion_inicial)
    agente_despues.ejecutar_turno(pedidos)
    print("Después del evento:", resumen_agente(agente_despues.state))

    explicacion = explicar_evento_disruptor(evento_info, agente_antes.state, agente_despues.state)
    print("\nExplicación de Gemini (stub):")
    print(explicacion)