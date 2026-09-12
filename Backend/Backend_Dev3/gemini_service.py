import os
from google import genai
from google.genai import types
from schemas import SolicitudMediacion

class GeminiMediator:
    def __init__(self):
        # Toma automáticamente la variable GEMINI_API_KEY cargada por load_dotenv()
        self.client = genai.Client()
        self.model_name = "gemini-3.6-flash"

    def evaluar_y_decidir(self, datos: SolicitudMediacion) -> str:
        prompt = f"""
        Eres el sistema de inteligencia logística 'CourierAI' operando en Monterrey, Nuevo León.
        Tu objetivo es evaluar dos rutas y justificar la mejor opción para el repartidor en tiempo real.

        [CONDICIONES EN MONTERREY]
        Evento actual: {datos.evento_contexto}

        [OPCIÓN 1 - AGENTE BASELINE]
        Ruta propuesta: {", ".join(datos.opcion_baseline.ruta_nodos)}
        Tiempo estimado: {datos.opcion_baseline.tiempo_est_min} minutos
        Ganancia neta: ${datos.opcion_baseline.ganancia_neta_mxn} MXN
        Lógica del agente: {datos.opcion_baseline.argumento_agente}

        [OPCIÓN 2 - AGENTE SMART (OR-TOOLS)]
        Ruta propuesta: {", ".join(datos.opcion_smart.ruta_nodos)}
        Tiempo estimado: {datos.opcion_smart.tiempo_est_min} minutos
        Ganancia neta: ${datos.opcion_smart.ganancia_neta_mxn} MXN
        Lógica del agente: {datos.opcion_smart.argumento_agente}

        INSTRUCCIONES DE RESPUESTA:
        1. Confirma que la Opción 2 (Smart) es la elegida debido a su eficiencia matemática y rentabilidad.
        2. Explica brevemente (máximo 3 oraciones) por qué esta decisión es superior considerando las vialidades y el evento en Monterrey.
        3. Mantén un tono profesional, claro y directo para la pantalla del repartidor.
        """

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2
                )
            )
            return response.text
        except Exception as e:
            print(f"\n❌ ERROR LLAMANDO A GEMINI: {e}\n")
            raise e