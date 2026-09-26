FROM python:3.12-slim

WORKDIR /app

# Built from parte2_infraestructura_datos/ as build context, same as
# site_api/Dockerfile, so that src.common is available without an
# installable package.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/common ./src/common
COPY src/coordinator ./src/coordinator

EXPOSE 8000

CMD ["uvicorn", "src.coordinator.main:app", "--host", "0.0.0.0", "--port", "8000"]
