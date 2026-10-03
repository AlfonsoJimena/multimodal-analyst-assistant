# =====================================================================
# Imagen del chatbot (P3-14): la misma para la API, la interfaz y el mock.
#
# Se construye con parte3_agente_conversacional/ como contexto (lo fijan
# los compose: context: ..), asi `src.*` y `mock.*` importan igual que en
# local y en los tests. El .dockerignore de ese directorio deja fuera el
# .env, los tests y los resultados de evaluacion.
#
# No tiene CMD: el comando de cada servicio lo fija su compose.
# =====================================================================

FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Configuracion de Streamlit: se lee del directorio de trabajo (/app).
COPY .streamlit ./.streamlit
COPY src ./src
COPY mock ./mock

# API del agente, interfaz y coordinador mock.
EXPOSE 8300 8501 8190
