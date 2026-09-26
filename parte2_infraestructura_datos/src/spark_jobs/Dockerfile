# Imagen para los jobs de Spark de una sede (stream_bronze / silver / sink_postgres).
# pyspark (pip) necesita una JVM, por eso instalamos un JRE.
# El job concreto se selecciona con 'command' en docker-compose.site.yml.
# Base fijada a Debian 12 (bookworm): la etiqueta python:3.12-slim pasó a
# Debian 13 (trixie), que ya no incluye openjdk-17-jre-headless.
FROM python:3.12-slim-bookworm

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends openjdk-17-jre-headless \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/common ./src/common
COPY src/spark_jobs ./src/spark_jobs

# Por defecto arranca la ingesta desde Kafka; los otros jobs se lanzan
# con su propio 'command' en el compose.
CMD ["python", "-m", "src.spark_jobs.stream_bronze"]
