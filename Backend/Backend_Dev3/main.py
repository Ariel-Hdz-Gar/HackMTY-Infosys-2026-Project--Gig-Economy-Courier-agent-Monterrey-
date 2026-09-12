from fastapi import FastAPI
from dotenv import load_dotenv
from schemas import SolicitudMediacion, RespuestaMediacion
from gemini_service import GeminiMediator

# Carga las variables de entorno desde el archivo .env
load_dotenv()

app = FastAPI(
    title="CourierAI - Módulo de IA Mediador",
    description="Microservicio para la evaluación de rutas y generación de explicabilidad con Gemini API"
)

# Instanciamos nuestra clase mediadora
mediador = GeminiMediator()

@app.get("/")
def home():
    return {"status": "ok", "mensaje": "Servidor de CourierAI Mediador activo"}

@app.post("/evaluar-rutas", response_model=RespuestaMediacion)
async def evaluar_rutas(solicitud: SolicitudMediacion):
    # Procesa la solicitud usando Gemini
    veredicto_texto = mediador.evaluar_y_decidir(solicitud)
    
    return RespuestaMediacion(
        agente_ganador=solicitud.opcion_smart.agente,
        explicacion_gemini=veredicto_texto
    )