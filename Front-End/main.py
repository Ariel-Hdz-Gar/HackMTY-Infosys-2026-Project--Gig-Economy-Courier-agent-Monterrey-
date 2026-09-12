import streamlit as st
import folium
from streamlit_folium import st_folium
import psycopg2
import os
from dotenv import load_dotenv
import time
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "Backend", "Backend_Dev2"))

from Motor_Matematico import SmartAgent, BaselineAgent, activar_evento
from Tiger_Data_io import leer_pedidos_pendientes, sincronizar_log_completo

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
            # Extraer ganancias
            cursor.execute("SELECT SUM(monto) FROM transactions WHERE agente = 'smart'")
            ganancia_smart = cursor.fetchone()[0] or 0.0
            
            cursor.execute("SELECT SUM(monto) FROM transactions WHERE agente = 'baseline'")
            ganancia_baseline = cursor.fetchone()[0] or 0.0

            # Extraer rutas
            cursor.execute("SELECT latitud, longitud FROM driver_logs WHERE agente = 'smart' ORDER BY id ASC")
            ruta_smart = cursor.fetchall() 
            
            cursor.execute("SELECT latitud, longitud FROM driver_logs WHERE agente = 'baseline' ORDER BY id ASC")
            ruta_baseline = cursor.fetchall()
            
            # Extraer orden activa
            cursor.execute("SELECT id, estado_ciudad FROM orders WHERE status = 'PENDIENTE' ORDER BY id DESC LIMIT 1")
            orden_actual = cursor.fetchone()
            
            orden_id = orden_actual[0] if orden_actual else 0
            evento_actual = orden_actual[1] if orden_actual else "normal"

        # Proteccion: Si no hay rutas aun, poner coordenadas por defecto de Monterrey
        if not ruta_smart: ruta_smart = [[25.6714, -100.3168]]
        if not ruta_baseline: ruta_baseline = [[25.6714, -100.3168]]

        return ruta_smart, ruta_baseline, ganancia_smart, ganancia_baseline, evento_actual, orden_id
    except Exception as e:
        st.error(f"Error en consulta: {e}")
        return [[25.6714, -100.3168]], [[25.6714, -100.3168]], 0.0, 0.0, "normal", 0

ruta_smart, ruta_baseline, ganancia_smart, ganancia_baseline, evento_actual, orden_id = obtener_datos_tiger()
razonamiento_smart = "Esperando decision de Gemini..."

# ==========================================
# 3. INTERFAZ VISUAL
# ==========================================
st.markdown("<h1 style='text-align: center; color: #00FF80;'>CourierAI - Gig Economy Simulator</h1>", unsafe_allow_html=True)
st.markdown("---")

col_roja, col_azul, col_naranja = st.columns([1, 2, 1])

# --- AREA ROJA ---
with col_roja:
    st.header("Decision en Vivo")
    
    st.subheader("Agente Baseline")
    st.error(f"Aceptando orden #{orden_id}. \n\nRuta directa sin considerar eventos dinamicos.")
    
    st.subheader("Agente Inteligente (Gemini)")
    st.success(razonamiento_smart)

# --- AREA AZUL (MAPA) ---
with col_azul:
    mapa_mty = folium.Map(location=ruta_smart[-1], zoom_start=15, tiles="OpenStreetMap")
    
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