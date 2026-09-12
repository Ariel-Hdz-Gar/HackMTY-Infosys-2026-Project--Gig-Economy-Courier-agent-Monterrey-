import streamlit as st
import folium
from streamlit_folium import st_folium
import psycopg2
import os
from dotenv import load_dotenv
import time
import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend", "Backend_Dev2"))

from Motor_Matematico import SmartAgent, BaselineAgent, activar_evento, obtener_ruta_coordenadas
from Tiger_Data_io import leer_pedidos_pendientes, sincronizar_log_completo
from Debate_Rutas import debatir_rutas, generar_opciones_ruta
from Motor_Matematico import Order

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend", "Backend_Dev1"))
from generator import generate_single_order, load_or_create_graph

# Cargar el mapa de Monterrey una sola vez
@st.cache_resource
def obtener_grafo():
    return load_or_create_graph()

G = obtener_grafo()

# En la barra lateral (Sidebar) de Streamlit:
if st.sidebar.button("⚡ Generar Nueva Orden"):
    nueva_id = generate_single_order(G)
    st.sidebar.success(f"¡Orden #{nueva_id} generada en Tiger Data!")

# ==========================================
# 1. CONFIGURACION DE PAGINA
# ==========================================
st.set_page_config(page_title="CourierAI Demo", layout="wide")

# ==========================================
# 2. CONEXION A DATOS (Tiger Data Real)
# ==========================================
load_dotenv()

@st.cache_resource
def inicializar_conexion():
    try:
        return psycopg2.connect(os.environ.get("DATABASE_URL"))
    except Exception as e:
        st.error(f"Error conectando a Tiger Data: {e}")
        st.stop()

conexion = inicializar_conexion()

def obtener_datos_tiger():
    try:
        with conexion.cursor() as cursor:
            # Ganancias
            cursor.execute("SELECT SUM(net_profit) FROM transactions WHERE agent_type = 'SMART'")
            ganancia_smart = cursor.fetchone()[0] or 0.0

            cursor.execute("SELECT SUM(net_profit) FROM transactions WHERE agent_type = 'BASELINE'")
            ganancia_baseline = cursor.fetchone()[0] or 0.0

            # Orden activa, Evento y Coordenadas
            cursor.execute(
                "SELECT id, event_type, origin_lat, origin_lon, dest_lat, dest_lon "
                "FROM orders WHERE status = 'PENDIENTE' ORDER BY id DESC LIMIT 1"
            )
            orden_actual = cursor.fetchone()

            if orden_actual:
                orden_id = orden_actual[0]
                evento_actual = orden_actual[1] or "normal"
                # Usamos el origen y destino de la orden como ruta temporal
                ruta_smart = obtener_ruta_coordenadas(
                    (orden_actual[2], orden_actual[3]),   # origen
                    (orden_actual[4], orden_actual[5]),   # destino
                ) 
                ruta_baseline = ruta_smart
            else:
                orden_id = 0
                evento_actual = "normal"
                ruta_smart = [[25.6714, -100.3168]]
                ruta_baseline = [[25.6714, -100.3168]]

        return ruta_smart, ruta_baseline, ganancia_smart, ganancia_baseline, evento_actual, orden_id

    except Exception as e:
        conexion.rollback() 
        st.error(f"Error en consulta: {e}")
        return [[25.6714, -100.3168]], [[25.6714, -100.3168]], 0.0, 0.0, "normal", 0

ruta_smart, ruta_baseline, ganancia_smart, ganancia_baseline, evento_actual, orden_id = obtener_datos_tiger()
    
# ==========================================
# EVALUACION DINAMICA (Baseline vs Smart con Gemini)
# ==========================================
posicion_actual = tuple(ruta_smart[-1])

# Convertir la orden pendiente actual en objeto Order para el debate
if orden_id != 0:
    pedido_activo = [Order(str(orden_id), tuple(ruta_smart[0]), tuple(ruta_smart[-1]), 50.0, 1800)]
    opciones = generar_opciones_ruta(posicion_actual, pedido_activo, k=2)
    debate = debatir_rutas(opciones)
    razonamiento_smart = debate.get("veredicto_mediador", "Evaluando ruta con Gemini...")
else:
    razonamiento_smart = "Sin órdenes pendientes en el sistema."

# ==========================================
# 3. INTERFAZ VISUAL
# ==========================================
st.markdown("<h1 style='text-align: center; color: #00FF80;'>CourierAI - Gig Economy Simulator</h1>", unsafe_allow_html=True)
st.markdown("---")

col_roja, col_azul, col_naranja = st.columns([1, 2, 1])

# --- AREA ROJA ---
with col_roja:
    st.header("Decisión en Vivo")
    
    st.subheader("🤖 Agente Baseline")
    st.error(f"Orden #{orden_id} activa\n\n• Estrategia: Voraz (Distancia mínima fija)\n• Penalizaciones dinámicas: Ignoradas")
    
    st.subheader("🧠 Agente Smart")
    st.success(f"Orden #{orden_id} activa\n\n• Estrategia: Optimización Multivariable\n• Ajuste: Clima/Tráfico integrados")

    st.subheader("⚖️ Veredicto de Gemini")
    st.info(razonamiento_smart)

# --- AREA AZUL (MAPA) ---
with col_azul:
    mapa_mty = folium.Map(
        location=ruta_smart[-1], 
        zoom_start=14, 
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri"
    )
    
    # Ruta y marcador Inteligente
    folium.PolyLine(locations=ruta_smart, color="#00FF80", weight=5, opacity=0.9).add_to(mapa_mty)
    folium.Marker(location=ruta_smart[-1], popup="Smart", icon=folium.Icon(color="green", icon="motorcycle", prefix="fa")).add_to(mapa_mty)

    # Ruta y marcador Baseline
    folium.PolyLine(locations=ruta_baseline, color="#FF4B4B", weight=5, opacity=0.9, dash_array="10").add_to(mapa_mty)
    folium.Marker(location=ruta_baseline[-1], popup="Baseline", icon=folium.Icon(color="red", icon="motorcycle", prefix="fa")).add_to(mapa_mty)
    
    st_folium(mapa_mty, use_container_width=True, height=500, returned_objects=[])

# --- AREA NARANJA ---
with col_naranja:
    st.header("Metricas")
    
    st.metric(label="Ganancia Neta (Inteligente)", value=f"${ganancia_smart} MXN")
    st.metric(label="Ganancia Neta (Baseline)", value=f"${ganancia_baseline} MXN")
    
    st.markdown("### Radar de Eventos")
    if evento_actual == "clima":
        st.warning("ALERTA CLIMATICA: Lluvia detectada en la zona.")
    elif evento_actual == "trafico":
        st.error("BLOQUEO VIAL: Embotellamiento severo reportado.")
    else:
        st.info("ESTADO NORMAL: Condiciones optimas.")

# ==========================================
# 4. CICLO DE ACTUALIZACION
# ==========================================
time.sleep(2)
st.rerun()