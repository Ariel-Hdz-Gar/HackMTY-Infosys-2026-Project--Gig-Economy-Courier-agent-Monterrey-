"""
CourierAI - Motor Matemático (Dev 2)
--------------------------------------
Contiene:
  - Contrato de datos (Order, AgentState)
  - Agente Baseline (FIFO, sin filtrar rentabilidad)
  - Agente Inteligente (OR-Tools CP-SAT: selección de pedidos por margen
    neto + batching por cercanía con TSP corto)
  - Hook de evento disruptor (bloqueo vial / lluvia intensa)

INTEGRACIÓN CON DEV 1 (environment.py):
  distancia_km() intenta usar el grafo vial real de Monterrey (OSMnx +
  networkx) que expone Dev 1 en Backend_Dev1/environment.py. Si ese módulo
  no está disponible (ej. corriendo este archivo solo, sin el resto del
  repo, o el .graphml aún no se descargó), cae automáticamente a una
  aproximación de línea recta (haversine) para que el motor NUNCA truene
  por falta del grafo — solo pierde precisión, no funcionalidad.
"""

import math
import time
import uuid
import sys
import os
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Optional

from ortools.sat.python import cp_model
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

logger = logging.getLogger("motor_matematico")


# ---------------------------------------------------------------------------
# 1. CONTRATO DE DATOS
# ---------------------------------------------------------------------------

@dataclass
class Order:
    order_id: str
    origen: tuple          # (lat, lon)
    destino: tuple          # (lat, lon)
    tarifa_base: float      # MXN
    tiempo_limite_s: int    # segundos disponibles para entregar
    timestamp_creacion: float = field(default_factory=time.time)
    evento: Optional[str] = None  # 'lluvia' | 'trafico' | None -- viene de
                                   # orders.estado_ciudad (Tiger Data), si Dev 1
                                   # ya agregó esa columna. Ver multiplicador_para().


@dataclass
class AgentState:
    nombre: str
    posicion: tuple
    ganancia_total: float = 0.0
    log: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. UTILIDADES DE DISTANCIA
#    Intenta usar el grafo real de Dev 1; si no está disponible, usa
#    haversine (línea recta) como respaldo silencioso.
# ---------------------------------------------------------------------------

def _haversine_km(p1: tuple, p2: tuple) -> float:
    lat1, lon1 = p1
    lat2, lon2 = p2
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# --- intento de importar el grafo real de Dev 1 ---
_GRAFO_DISPONIBLE = False
_GRAFO = None
_NODO_CACHE: Dict[tuple, int] = {}     # (lat_redondeada, lon_redondeada) -> node_id
_RUTA_CACHE: Dict[tuple, float] = {}   # (nodo1, nodo2) -> km

try:
    # Ajusta esta ruta si la estructura final de carpetas cambia.
    _ruta_dev1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "Backend_Dev1")
    if os.path.isdir(_ruta_dev1) and _ruta_dev1 not in sys.path:
        sys.path.append(_ruta_dev1)

    from environment import load_or_create_graph, get_nearest_node, calculate_route_distance

    _GRAFO_DISPONIBLE = True
except Exception as e:
    logger.warning(
        f"No se pudo importar environment.py de Dev 1 ({e}). "
        f"distancia_km() usará línea recta (haversine) como respaldo."
    )


def _get_grafo():
    global _GRAFO
    if _GRAFO is None:
        logger.info("Cargando grafo vial de Monterrey (puede tardar la primera vez)...")
        # Ruta ABSOLUTA al .graphml, sin importar desde qué carpeta esté
        # corriendo este proceso (Front-End corre desde otra carpeta que
        # Dev 1, así que una ruta relativa no lo encontraría).
        ruta_graphml = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..", "Backend_Dev1", "monterrey_drive.graphml",
        )
        _GRAFO = load_or_create_graph(filepath=ruta_graphml)
    return _GRAFO


def _nodo_cercano(lat: float, lon: float) -> int:
    clave = (round(lat, 5), round(lon, 5))
    if clave not in _NODO_CACHE:
        _NODO_CACHE[clave] = get_nearest_node(_get_grafo(), lat, lon)
    return _NODO_CACHE[clave]


def distancia_km(p1: tuple, p2: tuple) -> float:
    """Distancia entre dos coordenadas (lat, lon). Usa el grafo real de
    calles de Monterrey si Dev 1 lo dejó disponible; si no, aproxima con
    línea recta. Cachea resultados por par de nodos para no recalcular
    rutas repetidas (el batching y el TSP llaman esta función muchas veces)."""
    if _GRAFO_DISPONIBLE:
        try:
            n1 = _nodo_cercano(*p1)
            n2 = _nodo_cercano(*p2)
            if n1 == n2:
                return 0.0

            clave_ruta = (n1, n2) if n1 < n2 else (n2, n1)
            if clave_ruta not in _RUTA_CACHE:
                metros = calculate_route_distance(_get_grafo(), n1, n2)
                _RUTA_CACHE[clave_ruta] = (metros / 1000.0) if metros != float("inf") else None

            km = _RUTA_CACHE[clave_ruta]
            if km is not None:
                return km
            # sin ruta conectada en el grafo -> cae a haversine para no
            # inflar artificialmente el margen con 'infinito'
        except Exception as e:
            logger.warning(f"Fallo consultando el grafo real ({e}); usando haversine.")

    return _haversine_km(p1, p2)


def obtener_ruta_coordenadas(origen: tuple, destino: tuple) -> list:
    """Para el FRONTEND (Dev 4): regresa la lista de puntos [lat, lon] que
    sigue la ruta REAL sobre las calles de Monterrey entre origen y destino
    -- no solo los 2 extremos. Úsala en vez de armar 'ruta_smart' manualmente
    con [[origen], [destino]], porque eso dibuja una línea recta en el mapa
    en vez de seguir las calles.

    Ejemplo en main.py:
        from motor_matematico import obtener_ruta_coordenadas
        ruta_smart = obtener_ruta_coordenadas(
            (orden_actual[2], orden_actual[3]),   # origen
            (orden_actual[4], orden_actual[5]),   # destino
        )
        folium.PolyLine(locations=ruta_smart, ...).add_to(mapa_mty)

    Si el grafo real no está disponible, cae a una línea recta de 2 puntos
    (el mismo comportamiento que había antes) en vez de tronar.
    """
    if _GRAFO_DISPONIBLE:
        try:
            import networkx as nx
            grafo = _get_grafo()
            n1 = _nodo_cercano(*origen)
            n2 = _nodo_cercano(*destino)
            camino_nodos = nx.shortest_path(grafo, n1, n2, weight="length")
            return [[grafo.nodes[n]["y"], grafo.nodes[n]["x"]] for n in camino_nodos]
        except Exception as e:
            logger.warning(f"No se pudo calcular la ruta real ({e}); usando línea recta.")

    return [list(origen), list(destino)]


def obtener_ruta_coordenadas_evitando_eventos(origen: tuple, destino: tuple) -> list:
    """Como obtener_ruta_coordenadas(), pero para SMART: penaliza fuertemente
    las calles dentro de cualquier zona con evento activo (activar_evento),
    forzando al algoritmo a buscar un desvío en vez de cruzar directo por
    ahí. Baseline sigue usando obtener_ruta_coordenadas() normal -- ese es
    justo el contraste que quieres mostrar: Baseline va derecho sin pensar,
    Smart rodea el problema.

    Si no hay ninguna zona con evento activo en este momento, regresa
    exactamente la misma ruta que obtener_ruta_coordenadas() (no hay nada
    que evitar, así que no tiene sentido desviarse)."""
    if not _GRAFO_DISPONIBLE or not _penalizaciones_zona:
        return obtener_ruta_coordenadas(origen, destino)

    try:
        import networkx as nx
        grafo = _get_grafo()
        n1 = _nodo_cercano(*origen)
        n2 = _nodo_cercano(*destino)

        # Copia local de las zonas activas para no depender de closures raras
        zonas_activas = list(_penalizaciones_zona.keys())  # [(lat, lon, radio_km), ...]

        def _peso_evitando_zonas(u, v, datos_arista):
            longitud = datos_arista.get("length", 1.0)
            lat_u = grafo.nodes[u].get("y")
            lon_u = grafo.nodes[u].get("x")
            if lat_u is None or lon_u is None:
                return longitud
            for lat_z, lon_z, radio in zonas_activas:
                if _haversine_km((lat_u, lon_u), (lat_z, lon_z)) <= radio:
                    return longitud * 25.0  # penalización fuerte -> el algoritmo prefiere rodear
            return longitud

        camino_nodos = nx.shortest_path(grafo, n1, n2, weight=_peso_evitando_zonas)
        return [[grafo.nodes[n]["y"], grafo.nodes[n]["x"]] for n in camino_nodos]
    except Exception as e:
        logger.warning(f"No se pudo calcular ruta evitando eventos ({e}); usando ruta directa.")
        return obtener_ruta_coordenadas(origen, destino)


# ---------------------------------------------------------------------------
# 3. PARÁMETROS DE COSTO (calibrar en Horas 31-32)
# ---------------------------------------------------------------------------

COSTO_POR_KM = 4.5       # MXN, gasolina + desgaste
COSTO_POR_MINUTO = 0.8   # MXN, costo de oportunidad del tiempo
VELOCIDAD_KMH = 25.0     # velocidad promedio urbana

# multiplicador aplicado por zona cuando hay evento disruptor
_penalizaciones_zona: Dict[str, float] = {}


def margen_neto(order: Order, desde: tuple, multiplicador: float = 1.0) -> float:
    dist = distancia_km(desde, order.origen) + distancia_km(order.origen, order.destino)
    tiempo_min = (dist / VELOCIDAD_KMH) * 60
    costo = (dist * COSTO_POR_KM + tiempo_min * COSTO_POR_MINUTO) * multiplicador
    return order.tarifa_base - costo


_MULTIPLICADOR_POR_EVENTO = {"lluvia": 1.8, "trafico": 2.5}


def multiplicador_para(order: Order) -> float:
    """Prioridad: 1) el evento propio del pedido (order.evento, si viene
    poblado desde orders.estado_ciudad en Tiger Data) 2) las zonas activadas
    manualmente con activar_evento() (para el botón de la demo en vivo)."""
    if order.evento and order.evento in _MULTIPLICADOR_POR_EVENTO:
        return _MULTIPLICADOR_POR_EVENTO[order.evento]

    for zona, mult in _penalizaciones_zona.items():
        # zona simplificada como (lat, lon, radio_km)
        lat, lon, radio = zona
        if distancia_km((lat, lon), order.destino) <= radio:
            return mult
    return 1.0


# ---------------------------------------------------------------------------
# 4. AGENTE BASELINE
# ---------------------------------------------------------------------------

class BaselineAgent:
    """Acepta siempre la orden más antigua disponible, sin evaluar margen."""

    def __init__(self, posicion_inicial: tuple):
        self.state = AgentState(nombre="Baseline", posicion=posicion_inicial)

    def decidir(self, ordenes_pendientes: List[Order]) -> Optional[Order]:
        if not ordenes_pendientes:
            return None
        return min(ordenes_pendientes, key=lambda o: o.timestamp_creacion)

    def ejecutar(self, orden: Order):
        margen = margen_neto(orden, self.state.posicion)  # sin descartar negativos
        self.state.ganancia_total += margen
        self.state.posicion = orden.destino
        self.state.log.append({
            "orden_id": orden.order_id,
            "accion": "aceptado",
            "razon": "orden_mas_antigua",
            "margen": round(margen, 2),
        })


# ---------------------------------------------------------------------------
# 5. AGENTE INTELIGENTE (OR-Tools)
# ---------------------------------------------------------------------------

class SmartAgent:
    """
    Dos etapas:
      1) CP-SAT elige el subconjunto de pedidos que maximiza ganancia neta
         total, descartando los de margen negativo y respetando una ventana
         de tiempo total disponible (tiempo_limite_s).
      2) Para el subconjunto elegido, agrupa (batching) destinos cercanos y
         resuelve un TSP corto con OR-Tools routing para estimar el ahorro
         real de una ruta combinada vs. rutas individuales.
    """

    def __init__(self, posicion_inicial: tuple, tiempo_turno_s: int = 3600,
                 radio_batching_km: float = 1.5):
        self.state = AgentState(nombre="Inteligente", posicion=posicion_inicial)
        self.tiempo_disponible_s = tiempo_turno_s
        self.radio_batching_km = radio_batching_km

    # ---- Etapa 1: selección por margen y factibilidad de tiempo (CP-SAT) ----
    def seleccionar_ordenes(self, ordenes: List[Order]) -> List[Order]:
        evaluadas = []
        for o in ordenes:
            tiempo_est_s = (distancia_km(self.state.posicion, o.origen)
                             + distancia_km(o.origen, o.destino)) / VELOCIDAD_KMH * 3600

            # tiempo que le queda al pedido desde que se creó hasta su límite
            transcurrido_s = time.time() - o.timestamp_creacion
            tiempo_restante_s = o.tiempo_limite_s - transcurrido_s

            if tiempo_est_s > tiempo_restante_s:
                # ya no es físicamente alcanzable a tiempo: se descarta antes
                # de evaluar margen, ni el mejor precio salva un pedido tarde
                self.state.log.append({
                    "orden_id": o.order_id, "accion": "rechazado",
                    "razon": "tiempo_limite_excedido",
                    "tiempo_necesario_s": round(tiempo_est_s, 1),
                    "tiempo_restante_s": round(tiempo_restante_s, 1),
                })
                continue

            mult = multiplicador_para(o)
            margen = margen_neto(o, self.state.posicion, mult)
            if margen > 0:
                evaluadas.append((o, margen, tiempo_est_s))
            else:
                self.state.log.append({
                    "orden_id": o.order_id, "accion": "rechazado",
                    "razon": "margen_negativo", "valor": round(margen, 2),
                })

        if not evaluadas:
            return []

        model = cp_model.CpModel()
        x = [model.NewBoolVar(f"x_{i}") for i in range(len(evaluadas))]

        # restricción de tiempo total del turno
        model.Add(
            sum(int(t) * x[i] for i, (_, _, t) in enumerate(evaluadas))
            <= self.tiempo_disponible_s
        )

        # maximizar ganancia neta total (escalada a entero para CP-SAT)
        model.Maximize(
            sum(int(m * 100) * x[i] for i, (_, m, _) in enumerate(evaluadas))
        )

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 2.0
        status = solver.Solve(model)

        seleccionadas = []
        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            for i, (o, m, _) in enumerate(evaluadas):
                if solver.Value(x[i]) == 1:
                    seleccionadas.append(o)
                    self.state.log.append({
                        "orden_id": o.order_id, "accion": "aceptado",
                        "razon": "margen_positivo_optimizado", "margen": round(m, 2),
                    })
        return seleccionadas

    # ---- Etapa 2: batching por cercanía + TSP corto ----
    def agrupar_por_cercania(self, ordenes: List[Order]) -> List[List[Order]]:
        grupos: List[List[Order]] = []
        restantes = ordenes.copy()
        while restantes:
            base = restantes.pop(0)
            grupo = [base]
            for o in restantes.copy():
                if distancia_km(base.destino, o.destino) <= self.radio_batching_km:
                    grupo.append(o)
                    restantes.remove(o)
            grupos.append(grupo)
        return grupos

    def ruta_optima_grupo(self, grupo: List[Order]) -> float:
        """TSP corto (origen del agente + paradas del grupo). Devuelve
        distancia total en km de la ruta óptima combinada."""
        puntos = [self.state.posicion] + [o.destino for o in grupo]
        n = len(puntos)
        if n <= 2:
            return distancia_km(puntos[0], puntos[-1]) if n == 2 else 0.0

        manager = pywrapcp.RoutingIndexManager(n, 1, 0)
        routing = pywrapcp.RoutingModel(manager)

        def dist_cb(from_index, to_index):
            i = manager.IndexToNode(from_index)
            j = manager.IndexToNode(to_index)
            return int(distancia_km(puntos[i], puntos[j]) * 1000)  # metros

        transit_idx = routing.RegisterTransitCallback(dist_cb)
        routing.SetArcCostEvaluatorOfAllVehicles(transit_idx)

        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC)
        solution = routing.SolveWithParameters(params)
        if not solution:
            return sum(distancia_km(puntos[i], puntos[i + 1]) for i in range(n - 1))

        total_m = 0
        index = routing.Start(0)
        while not routing.IsEnd(index):
            nxt = solution.Value(routing.NextVar(index))
            total_m += routing.GetArcCostForVehicle(index, nxt, 0)
            index = nxt
        return total_m / 1000.0

    def ejecutar_turno(self, ordenes_pendientes: List[Order]):
        seleccionadas = self.seleccionar_ordenes(ordenes_pendientes)
        grupos = self.agrupar_por_cercania(seleccionadas)

        for grupo in grupos:
            dist_individual = sum(
                distancia_km(self.state.posicion, o.destino) for o in grupo)
            dist_combinada = self.ruta_optima_grupo(grupo)
            ahorro_km = max(0.0, dist_individual - dist_combinada)

            ganancia_grupo = sum(
                margen_neto(o, self.state.posicion, multiplicador_para(o))
                for o in grupo
            ) + ahorro_km * COSTO_POR_KM  # el ahorro de ruta se sale como ganancia extra

            self.state.ganancia_total += ganancia_grupo
            if grupo:
                self.state.posicion = grupo[-1].destino

            if len(grupo) > 1:
                self.state.log.append({
                    "accion": "batching",
                    "ordenes": [o.order_id for o in grupo],
                    "ahorro_km": round(ahorro_km, 2),
                })


# ---------------------------------------------------------------------------
# 6. EVENTO DISRUPTOR (para el botón "Bloqueo Vial" / "Lluvia Intensa")
# ---------------------------------------------------------------------------

def activar_evento(zona_centro: tuple, radio_km: float, tipo: str = "lluvia"):
    """Llamar cuando el usuario presiona el botón en la demo. Aumenta el
    costo efectivo de operar en la zona afectada; el próximo ciclo del
    SmartAgent recalculará automáticamente sus decisiones."""
    multiplicador = 1.8 if tipo == "lluvia" else 2.5  # bloqueo vial es peor
    _penalizaciones_zona[(zona_centro[0], zona_centro[1], radio_km)] = multiplicador
    return {"tipo": tipo, "zona": zona_centro, "radio_km": radio_km,
            "multiplicador": multiplicador}


def desactivar_eventos():
    _penalizaciones_zona.clear()


# ---------------------------------------------------------------------------
# 7. DEMO LOCAL (mock data, sin Tiger Data ni OSMnx)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    posicion_inicial = (25.6714, -100.3096)  # aprox. Centro de Monterrey

    ordenes_mock = [
        Order(str(uuid.uuid4())[:8], (25.671, -100.309), (25.665, -100.300), 65, 1800),
        Order(str(uuid.uuid4())[:8], (25.672, -100.310), (25.667, -100.301), 40, 1800),
        Order(str(uuid.uuid4())[:8], (25.669, -100.308), (25.700, -100.350), 30, 1200),  # margen negativo probable
        Order(str(uuid.uuid4())[:8], (25.673, -100.311), (25.666, -100.302), 55, 1800),
    ]

    baseline = BaselineAgent(posicion_inicial)
    orden = baseline.decidir(ordenes_mock)
    if orden:
        baseline.ejecutar(orden)

    smart = SmartAgent(posicion_inicial)
    smart.ejecutar_turno(ordenes_mock)

    print("=== BASELINE ===")
    print("Ganancia:", round(baseline.state.ganancia_total, 2))
    print(baseline.state.log)

    print("\n=== INTELIGENTE ===")
    print("Ganancia:", round(smart.state.ganancia_total, 2))
    for entry in smart.state.log:
        print(entry)

    print("\n--- Simulando evento disruptor (lluvia en zona de destinos) ---")
    activar_evento((25.666, -100.301), 1.0, tipo="lluvia")
    smart2 = SmartAgent(posicion_inicial)
    smart2.ejecutar_turno(ordenes_mock)
    print("Ganancia con evento activo:", round(smart2.state.ganancia_total, 2))