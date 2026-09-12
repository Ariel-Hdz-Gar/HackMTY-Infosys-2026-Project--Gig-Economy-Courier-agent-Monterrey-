import os
import sys
import random
import webbrowser
import folium
import networkx as nx

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, backend_dir)

from environment import load_or_create_graph, get_random_nodes, get_node_coords, calculate_route_distance

def create_interactive_map(output_file: str = "mapa_monterrey.html", num_orders: int = 5):
    print("📍 Cargando grafo vial de Monterrey desde backend...")
    graph_path = os.path.join(backend_dir, "monterrey_drive.graphml")
    G = load_or_create_graph(filepath=graph_path)
    
    # Coordenadas centrales de Monterrey (Macroplaza / Centro)
    mty_center = [25.6714, -100.3095]
    
    m = folium.Map(
        location=mty_center,
        zoom_start=12,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Tiles &copy; Esri &mdash; Source: Esri, DeLorme, NAVTEQ, USGS, Intermap, iPC, NRCAN, Esri Japan, METI, Esri China (Hong Kong), Esri (Thailand), TomTom"
    )
    
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors &copy; <a href='https://carto.com/attributions'>CARTO</a>",
        name="Carto Voyager",
        subdomains="abcd"
    ).add_to(m)
    
    colors = ['#FF5722', '#2196F3', '#9C27B0', '#E91E63', '#009688', '#FF9800', '#3F51B5']
    orders_data = []
    
    print(f"🚴 Generando {num_orders} órdenes simuladas con ruteo real en calles...")
    for i in range(1, num_orders + 1):
        nodes = get_random_nodes(G, n=2)
        orig_node, dest_node = nodes[0], nodes[1]
        
        orig_lat, orig_lon = get_node_coords(G, orig_node)
        dest_lat, dest_lon = get_node_coords(G, dest_node)
        
        try:
            route_nodes = nx.shortest_path(G, source=orig_node, target=dest_node, weight="length")
            distance_meters = nx.shortest_path_length(G, source=orig_node, target=dest_node, weight="length")
        except nx.NetworkXNoPath:
            continue
            
        km = distance_meters / 1000.0
        fare = round(max(40.0, min(200.0, 30.0 + (km * 12.0))), 2)
        color = colors[(i - 1) % len(colors)]
        
        route_coords = [get_node_coords(G, n) for n in route_nodes]
        
        folium.Marker(
            location=[orig_lat, orig_lon],
            popup=folium.Popup(
                f"""
                <div style="font-family: Arial; min-width: 180px;">
                    <b style="color: #2E7D32;">🟢 Punto de Recolección (Pickup)</b><br>
                    <b>Orden #{i}</b><br>
                    <b>Tarifa:</b> ${fare} MXN<br>
                    <b>Distancia:</b> {km:.2f} km<br>
                    <b>Nodo Origen:</b> {orig_node}
                </div>
                """, max_width=300
            ),
            tooltip=f"📦 Orden #{i} - Recolección (${fare} MXN)",
            icon=folium.Icon(color="green", icon="cutlery", prefix="fa")
        ).add_to(m)
        
        folium.Marker(
            location=[dest_lat, dest_lon],
            popup=folium.Popup(
                f"""
                <div style="font-family: Arial; min-width: 180px;">
                    <b style="color: #C62828;">🔴 Punto de Entrega (Destino)</b><br>
                    <b>Orden #{i}</b><br>
                    <b>Tarifa:</b> ${fare} MXN<br>
                    <b>Distancia:</b> {km:.2f} km<br>
                    <b>Nodo Destino:</b> {dest_node}
                </div>
                """, max_width=300
            ),
            tooltip=f"🏁 Orden #{i} - Entrega",
            icon=folium.Icon(color="red", icon="home", prefix="fa")
        ).add_to(m)
        
        folium.PolyLine(
            locations=route_coords,
            color=color,
            weight=5,
            opacity=0.85,
            tooltip=f"Ruta Orden #{i} ({km:.2f} km)"
        ).add_to(m)
        
        orders_data.append({
            "id": i,
            "fare": fare,
            "distance_km": round(km, 2),
            "orig_node": orig_node,
            "dest_node": dest_node
        })

    summary_html = f"""
    <div style="
        position: fixed; 
        top: 15px; 
        right: 15px; 
        width: 320px; 
        background: rgba(255, 255, 255, 0.95); 
        padding: 16px; 
        border-radius: 12px; 
        box-shadow: 0 4px 15px rgba(0,0,0,0.25);
        font-family: 'Segoe UI', Arial, sans-serif;
        z-index: 9999;
        font-size: 13px;
        line-height: 1.5;
    ">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="font-size: 20px;">🚀</span>
            <b style="font-size: 15px; color: #1E293B;">CourierAI - Dev 1 Monterrey</b>
        </div>
        <div style="background: #F1F5F9; padding: 8px; border-radius: 6px; margin-bottom: 10px;">
            <div>🗺️ <b>Grafo Vial:</b> Monterrey Completo</div>
            <div>📍 <b>Nodos:</b> 29,054 | 🛣️ <b>Aristas:</b> 72,910</div>
            <div>⚡ <b>Ruteo:</b> Red Vehicular Real (OSMnx)</div>
            <div>🐯 <b>DB Transaccional:</b> Tiger Data</div>
        </div>
        <b>Órdenes Simuladas Activas:</b>
        <ul style="margin: 4px 0 0 0; padding-left: 18px; max-height: 120px; overflow-y: auto;">
            {''.join([f"<li><b>Orden #{o['id']}:</b> {o['distance_km']} km &rarr; <span style='color:#16A34A;font-weight:bold;'>${o['fare']} MXN</span></li>" for o in orders_data])}
        </ul>
        <div style="margin-top: 10px; font-size: 11px; color: #64748B; text-align: center;">
            HackMTY 2026 &bull; Reto Infosys Track 1
        </div>
    </div>
    """
    m.get_root().html.add_child(folium.Element(summary_html))
    folium.LayerControl().add_to(m)
    
    out_path = os.path.join(os.path.dirname(__file__), output_file)
    m.save(out_path)
    abs_path = os.path.abspath(out_path)
    print(f"MAPA_GENERADO:{abs_path}")
    return abs_path

if __name__ == "__main__":
    filepath = create_interactive_map()
    print(f"\n✅ Mapa listo en: {filepath}")
