FROM python:3.12-slim

WORKDIR /app

# Built from parte2_infraestructura_datos/ as build context, so that
# src.common (imported by main.py, same as the Spark jobs) is
# available without needing an installable package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/common ./src/common
COPY src/site_api ./src/site_api

EXPOSE 8000

CMD ["uvicorn", "src.site_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
