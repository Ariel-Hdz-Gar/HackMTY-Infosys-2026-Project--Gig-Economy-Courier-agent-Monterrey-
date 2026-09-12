# 🚴 CourierAI — Simulación y Ruteo Inteligente en Monterrey
> **HackMTY 2026 — Reto Infosys (Track 1: Logística de Repartidores en Gig-Economy)**  
> **Reto Patrocinador:** Tiger Data (Base de Datos Relacional y Transaccional)  
> **Rol:** Dev 1: Entorno, Grafo Vial y Simulación (Backend)  
> **Rama:** `Dev1`

---

## 📋 Resumen del Rol: Dev 1 (Entorno y Simulación Backend)

Como **Dev 1**, la responsabilidad técnica abarca la base geoespacial y transaccional que alimenta a todo el escuadrón de desarrollo. Este módulo proporciona:

1. **Grafo Vial de Monterrey Cacheado (`environment.py`)**: Descarga y simplificación de la red vehicular de **todo Monterrey** mediante OSMnx (29,054 nodos y 72,910 calles). Al estar cacheado en `monterrey_drive.graphml`, optimiza la carga del sistema pasando de **45 segundos a ~3 segundos**.
2. **Infraestructura de Datos Tiger Data (`db/schema.sql` & `db/connection.py`)**: Diseño relacional que soporta la demanda (`orders`), telemetría en tiempo real (`driver_logs`) y el ledger contable de ganancias netas (`transactions`).
3. **Generador de Eventos en Streaming (`generator.py`)**: Simulación continua de pedidos ingresando al sistema con coordenadas reales en Monterrey y tarifas dinámicas en **$ MXN**.
4. **Visualizador Interactivo de Ruteo (`tools/visualize.py`)**: Generación de mapas HTML en vivo con Folium y mosaicos Esri para validar las trayectorias de los repartidores.

---

## 🏗️ Arquitectura y Flujo de Datos

```mermaid
flowchart TD
    OSM[OpenStreetMap / OSMnx] -->|Descarga red vehicular| ENV[environment.py]
    ENV -->|Genera caché local| GRAPH[monterrey_drive.graphml]
    
    GRAPH -->|Muestreo de Nodos| GEN[generator.py]
    GEN -->|Inserta órdenes en PENDIENTE| TD[(Tiger Data / PostgreSQL)]
    
    TD -->|Órdenes Disponibles| DEV2[Dev 2: Motor OR-Tools]
    DEV2 -->|Actualiza posiciones| TD
    
    TD -->|Telemetría y Ledger| DEV4[Dev 4: Dashboard Streamlit]
    DEV2 -->|Decisiones de Ruteo| DEV3[Dev 3: Gemini AI Explicabilidad]
```

---

## 📂 Estructura del Módulo `Dev1`

```text
HackMTY-Infosys-2026-Project--Gig-Economy-Courier-agent-Monterrey-/
├── db/                         # Módulo de Base de Datos (Tiger Data)
│   ├── schema.sql              # DDL: Tablas orders, driver_logs y transactions
│   └── connection.py           # Gestor de conexión PostgreSQL/Tiger Data e init_db()
├── tools/                      # Herramientas de diagnóstico y demo
│   └── visualize.py            # Generador de mapas interactivos HTML (Folium + Esri)
├── environment.py              # Gestor del grafo vial de Monterrey y funciones de ruteo
├── generator.py                # Generador continuo de pedidos en streaming
├── requirements.txt            # Dependencias de Python (osmnx, networkx, psycopg2, folium)
├── .env.example                # Plantilla de variables de entorno
└── README.md                   # Documentación principal del proyecto
```

---

## 📊 Esquema de Base de Datos (Tiger Data)

### 1. Tabla `orders` (Demanda)
guarda los pedidos emitidos en Monterrey:
* `id` (SERIAL PRIMARY KEY)
* `origin_lat`, `origin_lon` / `dest_lat`, `dest_lon`: Coordenadas geográficas.
* `origin_node_id`, `dest_node_id`: IDs de nodos en el grafo vial OSMnx.
* `base_fare`: Tarifa calculada en $ MXN.
* `status`: `PENDIENTE`, `ACEPTADA`, `RECHAZADA`, `COMPLETADA`, `EXPIRADA`.
* `assigned_agent`: `BASELINE` o `SMART`.

### 2. Tabla `driver_logs` (Telemetría)
Monitorea la ubicación de las motos segundo a segundo para el frontend:
* `agent_type`: `BASELINE` vs `SMART`.
* `current_lat`, `current_lon`, `current_node_id`.
* `status`: `IDLE`, `MOVING_TO_PICKUP`, `DELIVERING`.

### 3. Tabla `transactions` (Ledger Financiero)
Demuestra la rentabilidad superior del agente inteligente:
* `order_id`: Orden completada.
* `gross_fare`, `operational_cost`, `net_profit`.

---

## ⚡ Guía de Instalación y Ejecución

### 1. Clonar el repositorio y configurar el entorno
```bash
git clone https://github.com/Ariel-Hdz-Gar/HackMTY-Infosys-2026-Project--Gig-Economy-Courier-agent-Monterrey-.git
cd HackMTY-Infosys-2026-Project--Gig-Economy-Courier-agent-Monterrey-
git checkout Dev1

python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configurar variables de entorno (`.env`)
Crea un archivo `.env` en la raíz (puedes basarte en `.env.example`):
```env
DATABASE_URL=postgres://tsdbadmin:q33z9gicarant7kc@tsfgwbki2d.w84nx9piyi.tsdb.cloud.timescale.com:39869/tsdb?sslmode=require
ORDER_INTERVAL_SECONDS=4
```

### 3. Inicializar la Base de Datos (Tiger Data)
```bash
python db/connection.py
```

### 4. Generar el Grafo Vial de Monterrey
```bash
python environment.py
```

### 5. Iniciar el Generador de Pedidos en Streaming
```bash
python generator.py
```

### 6. Visualizar el Mapa Interactivo
```bash
python tools/visualize.py
```

---

## 🤝 Contrato de Datos para el Equipo

* **Para Dev 2 (OR-Tools / Agentes)**:
  * Importa `environment.py` para usar `load_or_create_graph()`, `calculate_route_distance(G, u, v)` y `get_nearest_node(G, lat, lon)`.
  * Consulta la tabla `orders` filtrando por `status = 'PENDIENTE'`.
* **Para Dev 4 (Frontend / Streamlit)**:
  * Lee la posición en tiempo real desde la tabla `driver_logs`.
  * Lee el acumulado de ganancias desde la tabla `transactions`.