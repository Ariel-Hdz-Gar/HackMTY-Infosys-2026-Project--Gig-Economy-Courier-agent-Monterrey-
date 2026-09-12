"""Corre esto desde Backend_Dev2: python diagnostico_env.py"""
import os
from dotenv import load_dotenv, find_dotenv

print("Directorio actual (cwd):", os.getcwd())

ruta_encontrada = find_dotenv(usecwd=True)
print("¿python-dotenv encontró un .env?:", ruta_encontrada or "❌ NO ENCONTRÓ NINGUNO")

if ruta_encontrada:
    load_dotenv(ruta_encontrada)

print("TIGER_DATA_URL:", "✅ definida" if os.environ.get("TIGER_DATA_URL") else "❌ no definida")
print("DATABASE_URL:  ", "✅ definida" if os.environ.get("DATABASE_URL") else "❌ no definida")