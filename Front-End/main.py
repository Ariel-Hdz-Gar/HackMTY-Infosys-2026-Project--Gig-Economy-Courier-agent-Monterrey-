import streamlit as st
import folium
from streamlit_folium import st_folium
import psycopg2
import os
from dotenv import load_dotenv
import time
import sys, os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "Backend", "Backend_Dev2"))

from Motor_Matematico import SmartAgent, BaselineAgent, activar_evento, obtener_ruta_coordenadas, Order
from Tiger_Data_io import leer_pedidos_pendientes, sincronizar_log_completo, ejecutar_ciclo_completo
from Debate_Rutas import debatir_rutas, generar_opciones_ruta
from Gemini_Bridge import explicar_evento_con_dev3  # ajusta el nombre exacto de tu archivo

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

def obtener_ganancias_historicas():
    """Ganancia NETA ACUMULADA de cada agente.

    SMART: viene de 'transactions' -- son órdenes que de verdad se
    simularon y completaron en el mundo real de la demo.

    BASELINE: viene de 'decisiones', SUMANDO SOLO los pedidos que aceptó
    Y que Smart NO aceptó también. Esto es consistente con el panel de
    'Decisión en Vivo': si Smart también quería el mismo pedido, Smart se
    lo gana (mejor opción) y ese pedido NO cuenta como ganancia de
    Baseline, aunque su algoritmo interno lo haya marcado 'aceptado'."""
    try:
        with conexion.cursor() as cursor:
            cursor.execute("SELECT SUM(net_profit) FROM transactions WHERE agent_type = 'SMART'")
            ganancia_smart = cursor.fetchone()[0] or 0.0

            cursor.execute("""
                SELECT SUM(d1.margen_neto)
                FROM decisiones d1
                WHERE d1.agente = 'BASELINE' AND d1.accion = 'aceptado'
                  AND NOT EXISTS (
                      SELECT 1 FROM decisiones d2
                      WHERE d2.order_id = d1.order_id
                        AND d2.agente = 'SMART'
                        AND d2.accion = 'aceptado'
                  )
            """)
            ganancia_baseline = cursor.fetchone()[0] or 0.0

        return ganancia_smart, ganancia_baseline
    except Exception as e:
        conexion.rollback()
        st.error(f"Error en consulta: {e}")
        return 0.0, 0.0

ganancia_smart, ganancia_baseline = obtener_ganancias_historicas()

# ==========================================
# EVALUACION DINAMICA (Baseline vs Smart sobre la MISMA orden)
# ==========================================
POSICION_BASE = (25.6714, -100.3096)

pedidos = leer_pedidos_pendientes(limit=50)

if pedidos:
    ids_actuales = tuple(sorted(p.order_id for p in pedidos))

    # --- Procesa el backlog completo (bookkeeping real -- no se dibuja) ---
    # Esto es lo que de verdad mueve las métricas: marca ACEPTADA/RECHAZADA
    # en Tiger Data, y alimenta al simulator.py de Dev 1 para que, con el
    # tiempo, la ganancia histórica de arriba suba.
    if st.session_state.get("ultimos_ids_pedidos") != ids_actuales:
        baseline_state, smart_state, _ = ejecutar_ciclo_completo(
            posicion_inicial=POSICION_BASE, pedidos=pedidos
        )
        st.session_state["ultimos_ids_pedidos"] = ids_actuales
        st.session_state["baseline_state"] = baseline_state
        st.session_state["smart_state"] = smart_state

    baseline_state = st.session_state.get("baseline_state")
    smart_state = st.session_state.get("smart_state")

    # --- La ORDEN ACTIVA para mostrar en pantalla: la más antigua pendiente ---
    # (leer_pedidos_pendientes ya viene ordenada ASC por timestamp_creacion,
    # así que pedidos[0] es justo la que BaselineAgent elegiría también.)
    orden_activa = pedidos[0]
    ruta_activa = obtener_ruta_coordenadas(orden_activa.origen, orden_activa.destino)
    evento_actual = orden_activa.evento or "normal"

    # Baseline: siempre "aceptaría" cualquier cosa (su algoritmo real no
    # cambia), pero para la vitrina de "Decisión en Vivo" sobre ESTA orden
    # específica, si Smart también la quiere, Smart se la gana (mejor
    # opción) y Baseline se muestra como que la perdió.
    decision_smart = next(
        (e for e in smart_state.log if e.get("orden_id") == orden_activa.order_id),
        {"accion": "desconocido", "razon": "no evaluada en este ciclo"},
    )

    # El margen REAL que Baseline calculó para esta orden (su algoritmo
    # siempre la evalúa, gane o pierda el pedido contra Smart).
    decision_baseline_real = next(
        (e for e in baseline_state.log if e.get("orden_id") == orden_activa.order_id),
        {"margen": None},
    )
    margen_baseline = decision_baseline_real.get("margen")

    if decision_smart.get("accion") == "aceptado":
        decision_baseline = {
            "accion": "rechazado",
            "razon": "Smart se quedó con este pedido (mejor opción)",
            "margen": margen_baseline,
        }
    else:
        decision_baseline = {
            "accion": "aceptado",
            "razon": "orden_mas_antigua",
            "margen": margen_baseline,
        }

    # Ambos agentes usan la MISMA ruta (mismo origen/destino) -- la
    # diferencia está en accion/razon, no en las coordenadas.
    ruta_smart = ruta_activa
    ruta_baseline = ruta_activa
    posicion_actual = tuple(ruta_activa[-1])

    # --- Veredicto de Gemini: limitado por TIEMPO, no por cambios de pedidos ---
    SEGUNDOS_MIN_ENTRE_LLAMADAS_GEMINI = 90
    ahora = time.time()
    ultima_llamada = st.session_state.get("ultima_llamada_gemini_ts", 0)

    if (ahora - ultima_llamada) >= SEGUNDOS_MIN_ENTRE_LLAMADAS_GEMINI and baseline_state and smart_state:
        resultado_gemini = explicar_evento_con_dev3(
            evento_texto=f"Condición actual en Monterrey: {evento_actual}",
            pedidos=pedidos,
            baseline_state=baseline_state,
            smart_state=smart_state,
        )
        st.session_state["ultima_llamada_gemini_ts"] = ahora
        st.session_state["ultimo_veredicto_texto"] = resultado_gemini.get(
            "explicacion_gemini", "Evaluando con Gemini..."
        )

    razonamiento_smart = st.session_state.get("ultimo_veredicto_texto", "Evaluando con Gemini...")

else:
    razonamiento_smart = "Sin órdenes pendientes en el sistema."
    ruta_smart = [[25.6714, -100.3168]]
    ruta_baseline = [[25.6714, -100.3168]]
    posicion_actual = tuple(ruta_smart[-1])
    orden_activa = None
    evento_actual = "normal"
    decision_baseline = {"accion": "sin_datos", "razon": ""}
    decision_smart = {"accion": "sin_datos", "razon": ""}

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
    if orden_activa:
        margen_txt = f"${decision_baseline.get('margen'):.2f}" if decision_baseline.get('margen') is not None else "N/A"
        if decision_baseline.get("accion") == "aceptado":
            st.error(
                f"Orden #{orden_activa.order_id}: ACEPTADA\n\n"
                f"• Estrategia: Voraz (Distancia mínima fija)\n"
                f"• Penalizaciones dinámicas: Ignoradas\n"
                f"• Margen: {margen_txt}"
            )
        else:
            st.warning(
                f"Orden #{orden_activa.order_id}: NO ASIGNADA\n\n"
                f"• Razón: {decision_baseline.get('razon')}\n"
                f"• Hubiera generado: {margen_txt}"
            )
    else:
        st.error("Sin órdenes pendientes.")

    st.subheader("🧠 Agente Smart")
    if orden_activa:
        if decision_smart.get("accion") == "aceptado":
            st.success(
                f"Orden #{orden_activa.order_id}: ACEPTADA\n\n"
                f"• Razón: {decision_smart.get('razon')}\n"
                f"• Margen: ${decision_smart.get('margen', 'N/A')}"
            )
        else:
            st.warning(
                f"Orden #{orden_activa.order_id}: RECHAZADA\n\n"
                f"• Razón: {decision_smart.get('razon')}"
            )
    else:
        st.success("Sin órdenes pendientes.")

    st.subheader("⚖️ Veredicto de Gemini")
    st.info(razonamiento_smart)

# --- AREA AZUL (MAPA) ---
with col_azul:
    import math

    def _desplazar_ruta(coords, metros=12, lado=1):
        """Desplaza una ruta lateralmente ~metros SOLO para dibujarla --
        Baseline y Smart pueden compartir la misma orden (mismo origen y
        destino real), y sin esto sus líneas quedarían exactamente
        superpuestas, tapándose una a la otra en el mapa."""
        if len(coords) < 2:
            return coords
        resultado = []
        n = len(coords)
        for i in range(n):
            if i < n - 1:
                lat2, lon2 = coords[i + 1]
                lat1, lon1 = coords[i]
            else:
                lat2, lon2 = coords[i]
                lat1, lon1 = coords[i - 1]
            dx, dy = lon2 - lon1, lat2 - lat1
            norma = math.hypot(dx, dy) or 1e-9
            perp_x, perp_y = -dy / norma, dx / norma
            factor = (metros / 111000.0) * lado
            resultado.append([coords[i][0] + perp_y * factor, coords[i][1] + perp_x * factor])
        return resultado

    mapa_mty = folium.Map(
        location=list(posicion_actual),
        zoom_start=14,
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}",
        attr="Esri"
    )

    ruta_baseline_dibujo = _desplazar_ruta(ruta_baseline, metros=12, lado=-1)
    ruta_smart_dibujo = _desplazar_ruta(ruta_smart, metros=12, lado=1)

    if decision_baseline.get("accion") == "aceptado":
        folium.PolyLine(locations=ruta_baseline_dibujo, color="#FF4B4B", weight=5, opacity=0.9).add_to(mapa_mty)
        folium.Marker(location=ruta_baseline_dibujo[-1], popup="Baseline (ganó el pedido)",
                      icon=folium.Icon(color="red", icon="motorcycle", prefix="fa")).add_to(mapa_mty)
    else:
        folium.PolyLine(locations=ruta_baseline_dibujo, color="#886666", weight=3, opacity=0.5, dash_array="4").add_to(mapa_mty)
        folium.Marker(location=ruta_baseline_dibujo[-1], popup="Baseline (perdió el pedido)",
                      icon=folium.Icon(color="lightgray", icon="ban", prefix="fa")).add_to(mapa_mty)

    if decision_smart.get("accion") == "aceptado":
        folium.PolyLine(locations=ruta_smart_dibujo, color="#00FF80", weight=5, opacity=0.9).add_to(mapa_mty)
        folium.Marker(location=ruta_smart_dibujo[-1], popup="Smart (aceptó)",
                      icon=folium.Icon(color="green", icon="motorcycle", prefix="fa")).add_to(mapa_mty)
    else:
        folium.PolyLine(locations=ruta_smart_dibujo, color="#AAAAAA", weight=4, opacity=0.7, dash_array="6").add_to(mapa_mty)
        folium.Marker(location=ruta_smart_dibujo[-1], popup="Smart (rechazó)",
                      icon=folium.Icon(color="gray", icon="ban", prefix="fa")).add_to(mapa_mty)

    st_folium(mapa_mty, use_container_width=True, height=500, returned_objects=[])

# --- AREA NARANJA ---
with col_naranja:
    st.header("Metricas")

    st.metric(label="Ganancia Neta (Inteligente)", value=f"${ganancia_smart:.2f} MXN")
    st.metric(label="Ganancia Neta (Baseline)", value=f"${ganancia_baseline:.2f} MXN")

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
time.sleep(15)
st.rerun()