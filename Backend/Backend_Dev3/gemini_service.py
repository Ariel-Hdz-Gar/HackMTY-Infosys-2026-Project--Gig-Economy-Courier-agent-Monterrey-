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
        Eres 'CourierAI', el sistema mediador de inteligencia logística para repartidores en Monterrey, Nuevo León.
        Tu trabajo es comparar dos propuestas de ruta y seleccionar LA MEJOR OPCIÓN objetivamente para el repartidor.

        [CONDICIONES DEL ENTORNO]
        Evento actual: {datos.evento_contexto}

        [OPCIÓN 1 - AGENTE BASELINE]
        - Ruta propuesta: {", ".join(datos.opcion_baseline.ruta_nodos)}
        - Tiempo estimado: {datos.opcion_baseline.tiempo_est_min} minutos
        - Ganancia neta: ${datos.opcion_baseline.ganancia_neta_mxn} MXN
        - Argumento del agente: {datos.opcion_baseline.argumento_agente}

        [OPCIÓN 2 - AGENTE SMART]
        - Ruta propuesta: {", ".join(datos.opcion_smart.ruta_nodos)}
        - Tiempo estimado: {datos.opcion_smart.tiempo_est_min} minutos
        - Ganancia neta: ${datos.opcion_smart.ganancia_neta_mxn} MXN
        - Argumento del agente: {datos.opcion_smart.argumento_agente}

        INSTRUCCIONES DE EVALUACIÓN:
        1. Compara ambas opciones evaluando: mayor ganancia neta, menor tiempo de traslado y menor riesgo ante el evento actual en Monterrey.
        2. Selecciona la mejor opción (ya sea Baseline o Smart) basándote estrictamente en cuál conviene más al repartidor.
        3. Redacta una justificación concisa (máximo 3 oraciones), profesional y directa para la pantalla del repartidor indicando claramente la opción ganadora y el porqué.
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
            return f"Error al generar decisión con Gemini: {str(e)}"