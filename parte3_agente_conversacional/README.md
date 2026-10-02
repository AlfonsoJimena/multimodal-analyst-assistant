# Parte 3 · Agente conversacional

Chatbot que responde preguntas en lenguaje natural sobre los datos de la
parte 2. Arquitectura y contratos en [`ARQUITECTURA.md`](ARQUITECTURA.md).

## Estructura

```
src/api/        contrato de /chat (schemas.py) y la API (main.py)
src/agent/      config, pasarela LLM, orquestador y prompt
src/tools/      formato/registro de herramientas (base.py) y herramientas
src/data/       cliente del coordinador, agregacion y privacidad
src/knowledge/  zonas de NYC, glosario y tipos de pago
src/ui/         interfaz Streamlit
mock/           coordinador falso para desarrollar sin la parte 2
tests/          tests unitarios (sin red) y de integracion (--integration)
```

## Puesta en marcha (desarrollo)

```bash
cd parte3_agente_conversacional
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env        # y rellena OPENROUTER_API_KEY
```

## Coordinador mock

Para desarrollar y probar el chatbot sin levantar la parte 2 (que ocupa
8-9 GB), `mock/` incluye un coordinador falso con el mismo contrato que el
real (incluido `breakdown=site`), servido desde fixtures deterministas.

```bash
# Desde parte3_agente_conversacional/
uvicorn mock.mock_coordinator:app --port 8190
```

Luego apunta `COORDINATOR_URLS=http://localhost:8190` en tu `.env`.

Fallos simulados con variables de entorno:

```bash
DOWN_SITES=atocha uvicorn mock.mock_coordinator:app --port 8190   # sede caida
SLOW_SITES=atocha SLOW_SECONDS=6 uvicorn mock.mock_coordinator:app --port 8190  # sede lenta
```

Regenerar las fixtures (deterministas, salen idénticas):

```bash
python -m mock.generar_fixtures
```

## Base de conocimiento y fuentes externas

`src/knowledge/` (P3-05) contiene lo que el agente sabe del dominio:

| Fichero | Contenido | Fuente |
|---|---|---|
| `taxi_zone_lookup.csv` | Las 265 zonas de taxi de NYC: ID, distrito, nombre y tipo de zona | [NYC TLC · Taxi Zone Lookup Table](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv), enlazada desde la [página de datos de la TLC](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) |
| `zones.py` | `zone_name(161)` → Midtown Center (Manhattan); `find_zone("jfk")` busca por nombre sin mayúsculas ni tildes | — |
| `payment_types.py` | Mapa único de códigos de pago (0–6) | [Diccionario de datos de la TLC](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf) (versión del 18/03/2025) |
| `glosario.md` | Sedes, métricas, qué viajes cuentan, fechas disponibles y qué no se puede responder | Parte 2 (`schema.py`, `cleaning.py`, `gold.py`) |

La tabla de zonas es una **fuente de datos externa** añadida a la parte 2:
los agregados solo traen `pu_location_id`, y con ella el agente puede
responder con nombres de zona ("Midtown Center, Manhattan") y aceptar
preguntas como "¿cuántos viajes salen de JFK?".

Para actualizarla:

```bash
curl -L -o src/knowledge/taxi_zone_lookup.csv \
  https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv
```

## Tests

```bash
# Desde parte3_agente_conversacional/
pytest                 # unitarios, sin red ni Docker
pytest --integration   # ademas, contra el coordinador real o el LLM
```

## Estado

En construccion por issues (ver etiqueta `parte3`). Bloque 1 (cimientos y
datos) → bloque 2 (herramientas) → bloque 3 (agente) → bloque 4 (interfaz y
despliegue) → bloque 5 (calidad y entrega).
