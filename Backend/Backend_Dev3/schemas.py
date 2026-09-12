from pydantic import BaseModel, Field

# 1. Estructura de la propuesta de ruta individual de cada agente
class PropuestaRuta(BaseModel):
    agente: str = Field(..., description="Nombre del agente, ej. 'Baseline' o 'Smart OR-Tools'")
    ruta_nodos: list[str] = Field(..., description="Lista de puntos/colonias de Monterrey")
    tiempo_est_min: int = Field(..., description="Tiempo estimado de viaje en minutos")
    ganancia_neta_mxn: float = Field(..., description="Ganancia neta esperada en pesos mexicanos")
    argumento_agente: str = Field(..., description="Razón básica por la que el agente eligió esta ruta")

# 2. Estructura de la petición completa que llegará a tu API (JSON de Entrada)
class SolicitudMediacion(BaseModel):
    evento_contexto: str = Field(..., description="Evento vial o climático en MTY, ej. 'Lluvia intensa en Av. Constitución'")
    opcion_baseline: PropuestaRuta
    opcion_smart: PropuestaRuta

# 3. Estructura de la respuesta que devolverá tu API (JSON de Salida)
class RespuestaMediacion(BaseModel):
    agente_ganador: str = Field(..., description="Nombre del agente con la decisión óptima")
    explicacion_gemini: str = Field(..., description="Veredicto final redactado por Gemini en lenguaje natural")