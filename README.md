<div align="center">

# CourierAI
### Autonomous AI Dispatch & Routing Agent for Last-Mile Logistics in Monterrey

[![Live Demo](https://img.shields.io/badge/🌐_LIVE_DEMO-Streamlit_AWS-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](http://54.89.200.159:8501)

[![HackMTY 2026](https://img.shields.io/badge/Hackathon-HackMTY%202026-orange.svg)](https://hackmty.com/)
[![Track Infosys](https://img.shields.io/badge/Track-Infosys-blue.svg)]()
[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/)
[![Timescale Cloud](https://img.shields.io/badge/Database-Timescale%20Cloud-0064a5.svg?logo=postgresql&logoColor=white)](https://www.timescale.com/)
[![Google Gemini](https://img.shields.io/badge/AI-Google%20Gemini%20API-4285F4.svg?logo=google&logoColor=white)](https://ai.google.dev/)
[![Streamlit](https://img.shields.io/badge/Frontend-Streamlit-FF4B4B.svg?logo=streamlit&logoColor=white)](https://streamlit.io/)

</div>

---

## Live Web Application & Demo

> [!IMPORTANT]
> **Experience CourierAI Live in Action:**
> 
>  **[http://54.89.200.159:8501](http://54.89.200.159:8501)**
> 
> *Hosted live on AWS EC2 featuring real-time Monterrey road map rendering, Gemini 2.5 Pro decision explainability, and live financial comparison metrics.*

---

## Overview

**CourierAI** is an autonomous AI-driven logistics simulation and routing platform designed for gig economy delivery couriers in **Monterrey, Mexico**.

Traditional last-mile delivery platforms rely on static greedy heuristics (Baseline) that fail to account for real-time traffic jams, severe weather disruptions, or dynamic operational cost structures. **CourierAI** bridges this gap by combining **graph-based spatial routing**, **Google Gemini LLM contextual reasoning**, **Google OR-Tools optimization**, and **Timescale Cloud time-series persistence** into an end-to-end multi-agent dispatch system.

---

##  System Architecture

The project is structured into four decoupled, microservice-like layers:

```
                  ┌─────────────────────────────────────────┐
                  │          Streamlit Dashboard            │
                  │   (Front_End / Folium Map Engine)       │
                  └────────────────────┬────────────────────┘
                                       │ Real-time UI & Metrics
                                       ▼
┌───────────────────────┐   ┌───────────────────────┐   ┌───────────────────────┐
│     Backend_Dev1      │   │     Backend_Dev2      │   │     Backend_Dev3      │
│  Environment Engine   │   │  Mathematical Engine  │   │  Gemini AI Mediator   │
│  - Monterrey OSMnx    │◄──┤  - OR-Tools Routing   ├──►│  - Gemini 2.5 Pro API │
│  - Order Streaming    │   │  - Baseline vs SMART  │   │  - Explanations       │
│  - Delivery Simulator │   │  - Decision Pipeline  │   │  - Decision Parsing   │
└───────────┬───────────┘   └───────────┬───────────┘   └───────────┬───────────┘
            │                           │
            └─────────────┬─────────────┘
                          ▼
            ┌───────────────────────────┐
            │   Tiger Data (Timescale)  │
            │   - orders (Spatial)      │
            │   - transactions (Ledger) │
            │   - driver_logs           │
            │   - decisiones            │
            └───────────────────────────┘
```

---

##  Key Features

-  **Real-World Monterrey Road Topology:** Built on OpenStreetMap (`OSMnx` & `NetworkX`) representing thousands of street nodes in Monterrey, N.L.
-  **Real-Time Order Generator & Simulator:** Streams simulated orders with dynamic fares, time windows, weather alerts, and automatic 20-second delivery lifecycle processing.
-  **Dual Agent Comparison (SMART vs Baseline):**
  - **Baseline Agent:** Greedy FIFO dispatch algorithm (nearest node / first-come-first-serve).
  - **SMART Agent:** Cost-aware decision engine backed by Google OR-Tools and dynamic risk pricing.
-  **Gemini 2.5 Pro Explainability Microservice:** Evaluates contextual events (e.g., heavy rain in Avenida Constitución) and generates natural language explanations for delivery decisions in 1-2 seconds (`temperature=0.0`).
-  **Tiger Data Cloud Persistence:** Stores live telemetry, transaction ledgers, net profit calculations, and decision logs on **Timescale Cloud (PostgreSQL)**.
-  **Interactive Map UI:** Renders live driver routes side-by-side using Folium with automatic offset polylines to prevent visual overlap.

---

##  Tech Stack

| Component | Technology |
|---|---|
| **Language** | Python 3.11+ |
| **Database & Storage** | Timescale Cloud / PostgreSQL (Tiger Data) |
| **GIS & Road Networks** | OSMnx, NetworkX, GeoPandas, Shapely |
| **Optimization & AI** | Google OR-Tools, Google Gemini API (`google-genai`), Scikit-Learn |
| **Microservices & API** | FastAPI, Uvicorn, Requests |
| **Frontend & UI** | Streamlit, Folium, `streamlit-folium`, Pandas |
| **DevOps & Cloud** | AWS EC2, Docker, Shell scripts (`Start.sh`) |

---

##  Repository Structure

```text
├── Backend/
│   ├── Backend_Dev1/          # Environment & Simulator (Dev 1)
│   │   ├── db/                # Tiger Data schema & PostgreSQL connection
│   │   ├── environment.py     # Monterrey OSMnx graph loader & synthetic fallback
│   │   ├── generator.py       # Real-time order streaming engine
│   │   ├── simulator.py       # Order lifecycle & transaction calculator
│   │   └── main.py            # Dev 1 master multi-threaded runner
│   ├── Backend_Dev2/          # Mathematical Decision Engine (Dev 2)
│   │   ├── Motor_Matematico.py# SMART Agent vs Baseline algorithms
│   │   ├── Tiger_Data_io.py   # DB read/write wrappers for decisions
│   │   └── Gemini_Bridge.py   # Client interface for Dev 3 microservice
│   └── Backend_Dev3/          # Gemini AI Microservice (Dev 3)
│       ├── gemini_service.py  # Fast Gemini 2.5 Pro decision engine
│       ├── main.py            # FastAPI server (/evaluar-rutas)
│       └── schemas.py         # Pydantic request/response schemas
├── Front_End/                 # Streamlit Live Dashboard (Dev 4)
│   └── main.py                # Main Streamlit + Folium map interface
├── Start.sh                   # One-click startup script for EC2 / Local
├── requirements.txt           # Unified dependency lockfile
└── README.md                  # Project documentation
```

---

## Database Schema (Tiger Data - Timescale Cloud)

```sql
-- Orders Table
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    origin_lat DOUBLE PRECISION, origin_lon DOUBLE PRECISION,
    dest_lat DOUBLE PRECISION, dest_lon DOUBLE PRECISION,
    base_fare NUMERIC(10, 2), status VARCHAR(20), event_type VARCHAR(30),
    expires_at TIMESTAMPTZ, created_at TIMESTAMPTZ, updated_at TIMESTAMPTZ
);

-- Financial Transactions Ledger
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    agent_type VARCHAR(30), gross_fare NUMERIC(10, 2),
    operational_cost NUMERIC(10, 2), net_profit NUMERIC(10, 2),
    completed_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Agent Decision Logs
CREATE TABLE decisiones (
    id BIGSERIAL PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    agente TEXT, accion TEXT, razon TEXT, margen_neto NUMERIC,
    timestamp TIMESTAMPTZ DEFAULT now()
);
```

---

##  Quick Start & Local Execution

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Ariel-Hdz-Gar/HackMTY-Infosys-2026-Project--Gig-Economy-Courier-agent-Monterrey-.git
cd HackMTY-Infosys-2026-Project--Gig-Economy-Courier-agent-Monterrey-

# Create virtual environment & install dependencies
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Variables (`.env`)
Create a `.env` file in the root directory:

```env
DATABASE_URL=postgres://user:password@host:port/database?sslmode=require
GEMINI_API_KEY=your_google_gemini_api_key
ORDER_INTERVAL_SECONDS=20
```

### 4. Running Services

Open 3 separate terminals:

```bash
# Terminal 1: Dev 1 Environment (Generator + Delivery Simulator)
python Backend/Backend_Dev1/main.py

# Terminal 2: Dev 3 Gemini Microservice
cd Backend/Backend_Dev3
uvicorn main:app --port 8000 --reload

# Terminal 3: Dev 4 Frontend Dashboard
streamlit run Front_End/main.py
```

*Or use the one-click startup script:*
```bash
chmod +x Start.sh
./Start.sh
```

---

##  Hackathon Credits

Developed for **HackMTY 2026** — **Track Infosys**:
- **Santiago (Dev 1):** Environment Simulation, OSMnx Road Networks & Timescale Cloud Database Architecture.
- **Dev 2:** Mathematical Engine, OR-Tools Optimization & Baseline vs SMART Heuristics.
- **Dev 3:** Google Gemini 2.5 Pro Microservice & Decision Explainability API.
- **Dev 4:** Streamlit Interactive UI, Folium Geospatial Rendering & AWS Deployment.

---

<div align="center">
  <b>Built with ❤️ at HackMTY 2026</b>
</div>
