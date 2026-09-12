"""
Corre esto desde Backend/Backend_Dev2 (con tu .env de Tiger Data ahí mismo):
  python3 prueba_tiger_real.py

Esto NO usa datos mock -- lee pedidos REALES pendientes de Tiger Data y
corre Baseline y Smart sobre ellos, exactamente como lo haría main.py.
Si aquí Smart sí tiene ganancia y log, el problema es 100% del frontend.
Si aquí Smart también sale vacío, el problema es de datos/consulta, no de
Streamlit.
"""
"""
Corre esto desde Backend/Backend_Dev2 (con tu .env de Tiger Data ahí mismo):
  python3 prueba_tiger_real.py

Esto NO usa datos mock -- lee pedidos REALES pendientes de Tiger Data y
corre Baseline y Smart sobre ellos, exactamente como lo haría main.py.
Si aquí Smart sí tiene ganancia y log, el problema es 100% del frontend.
Si aquí Smart también sale vacío, el problema es de datos/consulta, no de
Streamlit.
"""
import logging
logging.getLogger("motor_matematico").setLevel(logging.ERROR)  # silencia el spam de scikit-learn mientras diagnosticamos

from collections import Counter
from Tiger_Data_io import leer_pedidos_pendientes, ejecutar_ciclo_completo

pedidos = leer_pedidos_pendientes(limit=50)
print(f"Pedidos PENDIENTE leídos de Tiger Data: {len(pedidos)}")
for p in pedidos[:5]:
    print(f"  id={p.order_id} tarifa=${p.tarifa_base} tiempo_limite_s={p.tiempo_limite_s} evento={p.evento!r}")

print("\n--- Corriendo ambos agentes sobre esos mismos pedidos ---")
estado_baseline, estado_smart = ejecutar_ciclo_completo(posicion_inicial=(25.6714, -100.3096))

print(f"\nBASELINE: ganancia=${estado_baseline.ganancia_total:.2f} | {len(estado_baseline.log)} entradas en el log")
print(f"SMART:    ganancia=${estado_smart.ganancia_total:.2f} | {len(estado_smart.log)} entradas en el log")

# --- Desglose detallado de por qué Smart rechazó cada pedido ---
razones = Counter(e.get("razon") for e in estado_smart.log if e.get("accion") == "rechazado")
print("\nDesglose de razones de rechazo (Smart):")
for razon, cantidad in razones.most_common():
    print(f"  {razon}: {cantidad} pedidos")

print("\nPrimeros 5 rechazos con detalle completo:")
for e in [x for x in estado_smart.log if x.get("accion") == "rechazado"][:5]:
    print(" ", e)

if len(pedidos) == 0:
    print("\n⚠️  No hay pedidos PENDIENTE en la base -- por eso Smart no tiene nada que procesar.")
    print("   Revisa si generator.py (Dev 1) está corriendo y sigue insertando pedidos.")
elif estado_smart.ganancia_total == 0 and len(estado_smart.log) == 0:
    print("\n⚠️  Sí hay pedidos, pero Smart no generó NINGUNA entrada de log -- esto sería un bug real del motor, avísame.")
elif all(e.get("accion") == "rechazado" for e in estado_smart.log):
    print("\n⚠️  Smart SÍ corrió, pero rechazó TODOS los pedidos. Revisa el desglose de razones de arriba.")
else:
    print("\n✅ Smart está funcionando correctamente con datos reales. El problema es del frontend (no está mostrando esta info).")