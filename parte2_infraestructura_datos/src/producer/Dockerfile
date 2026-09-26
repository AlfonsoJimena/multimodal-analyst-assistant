# Imagen del producer de una sede.
# Build context = parte2_infraestructura_datos/ (igual que site_api),
# para que src.common este disponible sin empaquetar.
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/common ./src/common
COPY src/producer ./src/producer

# Los datos de entrada (data/prepared/<site>/realtime.csv) se montan en runtime.
CMD ["python", "-m", "src.producer.producer"]
