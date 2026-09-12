import os
import random
import logging
import networkx as nx
import osmnx as ox

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("environment")

GRAPH_FILEPATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "monterrey_drive.graphml"))
DEFAULT_PLACE = "Monterrey, Nuevo León, Mexico"


def generate_offline_fallback_graph(filepath: str = GRAPH_FILEPATH) -> nx.MultiDiGraph:
    """
    Genera un grafo vial sintético de Monterrey totalmente offline cuando la API de OpenStreetMap
    no está disponible o rechaza conexiones. Garantiza que la simulación NUNCA falle por red.
    """
    logger.warning("Generando grafo vial sintético de Monterrey (Modo Offline Backup)...")
    G = nx.MultiDiGraph()
    
    # Red de 25x25 nodos cubriendo Monterrey (lat: 25.55 a 25.75, lon: -100.40 a -100.20)
    lat_step = (25.75 - 25.55) / 24
    lon_step = (-100.20 - (-100.40)) / 24
    
    node_id = 1
    grid = {}
    for i in range(25):
        for j in range(25):
            lat = 25.55 + i * lat_step
            lon = -100.40 + j * lon_step
            grid[(i, j)] = node_id
            G.add_node(node_id, y=lat, x=lon, street_count=4)
            node_id += 1

    # Conectar nodos vecinos (calles bidireccionales)
    from environment import _haversine_km
    for (i, j), nid in grid.items():
        neighbors = []
        if i > 0: neighbors.append(grid[(i - 1, j)])
        if i < 24: neighbors.append(grid[(i + 1, j)])
        if j > 0: neighbors.append(grid[(i, j - 1)])
        if j < 24: neighbors.append(grid[(i, j + 1)])
        
        node_lat, node_lon = G.nodes[nid]["y"], G.nodes[nid]["x"]
        for neigh_id in neighbors:
            neigh_lat, neigh_lon = G.nodes[neigh_id]["y"], G.nodes[neigh_id]["x"]
            dist_meters = _haversine_km((node_lat, node_lon), (neigh_lat, neigh_lon)) * 1000.0
            G.add_edge(nid, neigh_id, length=dist_meters, travel_time=dist_meters / 10.0)

    # Guardar en archivo GraphML para uso local permanente
    try:
        ox.save_graphml(G, filepath=filepath)
        logger.info(f"¡Grafo sintético offline guardado en '{filepath}'! ({len(G.nodes)} nodos)")
    except Exception as e:
        logger.warning(f"No se pudo guardar el graphml sintético: {e}")
        
    return G


def _haversine_km(p1: tuple, p2: tuple) -> float:
    import math
    lat1, lon1 = p1
    lat2, lon2 = p2
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def download_monterrey_graph(place_name: str = DEFAULT_PLACE, filepath: str = GRAPH_FILEPATH) -> nx.MultiDiGraph:
    """
    Descarga la red vial de Monterrey con OSMnx o cae al generador offline si falla internet/Overpass API.
    """
    logger.info(f"Descargando grafo vial para: '{place_name}'...")
    try:
        G = ox.graph_from_place(place_name, network_type="drive", simplify=True)
        logger.info(f"Grafo descargado. Nodos: {len(G.nodes)}, Aristas: {len(G.edges)}")
        
        try:
            if hasattr(ox, "routing") and hasattr(ox.routing, "add_edge_speeds"):
                G = ox.routing.add_edge_speeds(G)
                G = ox.routing.add_edge_travel_times(G)
            elif hasattr(ox, "add_edge_speeds"):
                G = ox.add_edge_speeds(G)
                G = ox.add_edge_travel_times(G)
        except Exception as e:
            logger.warning(f"No se pudieron calcular travel_times automáticamente: {e}")

        logger.info(f"Guardando grafo en '{filepath}'...")
        ox.save_graphml(G, filepath=filepath)
        logger.info("¡Grafo guardado exitosamente!")
        return G
    except Exception as e:
        logger.error(f"Fallo descargando desde OpenStreetMap ({e}). Activando respaldo OFFLINE...")
        return generate_offline_fallback_graph(filepath=filepath)


def load_or_create_graph(filepath: str = GRAPH_FILEPATH, place_name: str = DEFAULT_PLACE) -> nx.MultiDiGraph:
    """
    Carga el grafo desde el archivo local .graphml si existe.
    Si no existe, intenta descargarlo o genera la versión sintética offline.
    """
    if os.path.exists(filepath):
        logger.info(f"Cargando grafo vial existente desde '{filepath}'...")
        try:
            G = ox.load_graphml(filepath=filepath)
            logger.info(f"Grafo cargado: {len(G.nodes)} nodos, {len(G.edges)} aristas.")
            return G
        except Exception as e:
            logger.warning(f"Error cargando archivo GraphML ({e}). Recreando...")
            
    return download_monterrey_graph(place_name=place_name, filepath=filepath)


def get_random_nodes(G: nx.MultiDiGraph, n: int = 1) -> list:
    """
    Retorna una lista de 'n' IDs de nodos aleatorios del grafo.
    """
    nodes_list = list(G.nodes())
    if not nodes_list:
        raise ValueError("El grafo no contiene nodos.")
    return random.sample(nodes_list, min(n, len(nodes_list)))


def get_node_coords(G: nx.MultiDiGraph, node_id) -> tuple:
    """
    Retorna (lat, lon) / (y, x) de un nodo específico.
    """
    node_data = G.nodes[node_id]
    return float(node_data["y"]), float(node_data["x"])


def get_random_coordinates(G: nx.MultiDiGraph, n: int = 1) -> list:
    """
    Retorna una lista de diccionarios con nodos y coordenadas aleatorias:
    [{'node_id': ..., 'lat': ..., 'lon': ...}, ...]
    """
    sampled_nodes = get_random_nodes(G, n)
    result = []
    for node in sampled_nodes:
        lat, lon = get_node_coords(G, node)
        result.append({
            "node_id": node,
            "lat": lat,
            "lon": lon
        })
    return result


def get_nearest_node(G: nx.MultiDiGraph, lat: float, lon: float):
    """
    Encuentra el nodo más cercano en el grafo para un par de coordenadas (lat, lon).
    """
    if hasattr(ox, "distance") and hasattr(ox.distance, "nearest_nodes"):
        return ox.distance.nearest_nodes(G, X=lon, Y=lat)
    elif hasattr(ox, "nearest_nodes"):
        return ox.nearest_nodes(G, X=lon, Y=lat)
    else:
        raise AttributeError("No se encontró el método nearest_nodes en osmnx.")


def calculate_route_distance(G: nx.MultiDiGraph, orig_node, dest_node, weight: str = "length") -> float:
    """
    Calcula la distancia mínima en metros (o peso seleccionado) entre dos nodos.
    """
    try:
        return nx.shortest_path_length(G, source=orig_node, target=dest_node, weight=weight)
    except nx.NetworkXNoPath:
        return float("inf")


if __name__ == "__main__":
    print("=== CourierAI: Inicialización de Entorno y Grafo Vial (Monterrey) ===")
    graph = load_or_create_graph()
    sample = get_random_coordinates(graph, n=2)
    print("\n--- Muestra de Coordenadas Aleatorias de Monterrey ---")
    print(f"Origen simulado : Nodo {sample[0]['node_id']} -> Lat: {sample[0]['lat']}, Lon: {sample[0]['lon']}")
    print(f"Destino simulado: Nodo {sample[1]['node_id']} -> Lat: {sample[1]['lat']}, Lon: {sample[1]['lon']}")
    
    dist = calculate_route_distance(graph, sample[0]['node_id'], sample[1]['node_id'])
    print(f"Distancia en red vial estimada: {dist:.2f} metros\n")
