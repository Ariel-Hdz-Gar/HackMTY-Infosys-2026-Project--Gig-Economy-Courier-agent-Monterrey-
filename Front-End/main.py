import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import time

# ==========================================
# SIMULADOR DE CONEXIÓN A TIGER DATA
# ==========================================
def obtener_datos():
    # Cuando el Dev 1 termine, borrarás estas dos líneas de abajo...
    with open("mock_tiger.json", "r", encoding="utf-8") as archivo:
        datos = json.load(archivo)
        
    # ...y las cambiarás por la consulta real a la base de datos.
    return datos

# 1. Traemos los datos frescos
db = obtener_datos()

# ==========================================
# ASIGNACIÓN DINÁMICA (Tu interfaz ahora es automática)
# ==========================================
ruta_smart = db["agente_inteligente"]["ruta_coordenadas"]
ruta_baseline = db["agente_baseline"]["ruta_coordenadas"]
evento_actual = db["estado_ciudad"]
razonamiento = db["agente_inteligente"]["razonamiento_ia"]

# A partir de aquí sigue todo tu código de st.columns(), los mapas y métricas...
# Solo asegúrate de usar estas variables (ej. st.success(razonamiento))

# ==========================================
# 1. CONFIGURACIÓN DE PÁGINA
# ==========================================
st.set_page_config(page_title="CourierAI Demo", layout="wide")

# ==========================================
# DATOS SIMULADOS (Lo que mandará el backend para ambos agentes)
# ==========================================
# Ruta del Agente Inteligente (Verde - Optimizada)
ruta_smart = [
    [25.6714, -100.3168], 
    [25.6720, -100.3150], 
    [25.6750, -100.3120]
]

# Ruta del Agente Baseline (Roja - Lineal/Ineficiente)
ruta_baseline = [
    [25.6714, -100.3168], 
    [25.6690, -100.3170], 
    [25.6650, -100.3180]
]

# ==========================================
# 2. ÁREA VERDE (Banner Superior)
# ==========================================
st.markdown("<h1 style='text-align: center; color: #00FF80;'>🚀 CourierAI - Gig Economy Simulator</h1>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# 3. DIVISIÓN DE PANTALLA
# ==========================================
col_roja, col_azul, col_naranja = st.columns([1, 2, 1])

# ==========================================
# 4. ÁREA ROJA (Izquierda): Razonamiento IAs
# ==========================================
with col_roja:
    st.header("🧠 Decisión en Vivo")
    
    st.subheader("Agente Baseline")
    st.error("Aceptando orden #102. \n\nRuta directa al cliente sin considerar el tráfico actual en Av. Constitución.")
    
    st.subheader("Agente Inteligente (Gemini)")
    st.success("Desviando ruta de orden #102. \n\nEvadiendo zona de tráfico severo y agrupando con orden #104 para mantener margen de ganancia positivo.")

# ==========================================
# 5. ÁREA AZUL (Centro): Mapa Folium
# ==========================================
with col_azul:
    # Inicializar el mapa centrado en el punto de partida
    mapa_mty = folium.Map(location=[25.6714, -100.3168], zoom_start=14, tiles="OpenStreetMap")
    
    # --- DIBUJAR AGENTE INTELIGENTE ---
    folium.PolyLine(
        locations=ruta_smart, color="#00FF80", weight=5, opacity=0.9
    ).add_to(mapa_mty)
    
    folium.Marker(
        location=ruta_smart[-1], # Se pone en la última coordenada de su ruta
        popup="Smart Agent",
        icon=folium.Icon(color="green", icon="motorcycle", prefix="fa")
    ).add_to(mapa_mty)

    # --- DIBUJAR AGENTE BASELINE ---
    folium.PolyLine(
        locations=ruta_baseline, color="#FF4B4B", weight=5, opacity=0.9, dash_array="10"
    ).add_to(mapa_mty)
    
    folium.Marker(
        location=ruta_baseline[-1],
        popup="Baseline Agent",
        icon=folium.Icon(color="red", icon="motorcycle", prefix="fa")
    ).add_to(mapa_mty)
    
    # Renderizar el mapa ajustado al ancho de la columna
    st_folium(mapa_mty, use_container_width=True, height=500, returned_objects=[])

# ==========================================
# 6. ÁREA NARANJA (Derecha): Controles / Métricas
# ==========================================
with col_naranja:
    st.header("📊 Métricas")
    
    st.metric(label="Ganancia Neta (Inteligente)", value="$450.00 MXN", delta="+$85 (Eficiencia)")
    st.metric(label="Ganancia Neta (Baseline)", value="$210.00 MXN", delta="-$15 (Tráfico)", delta_color="inverse")
    
    st.markdown("### 📡 Radar de Eventos Automáticos")
    # En lugar de botones, usamos alertas visuales que cambiarán según la variable que mande el backend
    
    # Simulación de un estado que el backend envía
    evento_actual = "trafico" 
    
    if evento_actual == "clima":
        st.warning("🌧️ **ALERTA CLIMÁTICA:** Lluvia detectada en Zona Sur. Reduciendo velocidad global 20%.")
    elif evento_actual == "trafico":
        st.error("🚧 **BLOQUEO VIAL:** Embotellamiento en Av. Constitución. Recalculando rutas afectadas.")
    else:
        st.info("✅ **ESTADO NORMAL:** Condiciones óptimas de operación.")

time.sleep(2) # Pausa de 2 segundos
st.rerun()