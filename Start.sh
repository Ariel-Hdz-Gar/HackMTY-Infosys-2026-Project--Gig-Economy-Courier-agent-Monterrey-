#!/bin/bash
set -e

echo "Iniciando Dev 1 (generador + simulador) en segundo plano..."
cd /app/Backend/Backend_Dev1
python main.py &

echo "Iniciando servicio de Gemini de Dev 3 en segundo plano (puerto 8000)..."
cd /app/Backend/Backend_Dev3
uvicorn main:app --host 0.0.0.0 --port 8000 &

# Le da un respiro al servicio de Dev 3 para levantar antes de que el
# Front-End intente hablarle (evita el ConnectionError de los primeros
# segundos mientras uvicorn arranca).
sleep 5

echo "Iniciando Front-End (Streamlit) en primer plano..."
cd /app/Front-End
exec streamlit run main.py --server.port=8501 --server.address=0.0.0.0 --server.fileWatcherType=none