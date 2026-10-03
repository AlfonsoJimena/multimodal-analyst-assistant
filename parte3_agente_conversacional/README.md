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

## Herramientas del agente

`src/tools/` (P3-06 y P3-07) contiene las herramientas cerradas que el LLM
puede llamar. Todas las cifras salen de aquí, nunca del modelo.

| Herramienta | Para qué | Bloque |
|---|---|---|
| `get_kpis` | Viajes, ingresos y medias de un periodo (filtra sedes y fechas) | `kpi` |
| `compare_sites` | Una fila por sede (demuestra el despliegue distribuido) | `bar` + `table` |
| `get_timeseries` | Serie por hora o por día de una métrica y su máximo | `line` |
| `get_payment_breakdown` | Viajes, ingresos y % por método de pago (acumulado) | `bar` + `table` |
| `get_zones` | Ranking de zonas de recogida con nombre y distrito (acumulado) | `table` |
| `get_zone` | Métricas de una zona, por ID o por nombre (acumulado) | `kpi` |
| `get_platform_status` | Réplicas vivas, sedes que responden y fechas con datos | `table` |

Reglas comunes: argumentos validados (los errores vuelven como `ToolError`,
nunca como excepción), `partial` respecto a las sedes pedidas, medias como
Σ sumas / Σ conteos y celdas con menos de `MIN_TRIPS_PER_CELL` viajes ocultas.

Llamarlas a mano, sin LLM (útil para depurar):

```bash
# Desde parte3_agente_conversacional/, con el mock levantado en 8190
export COORDINATOR_URLS=http://localhost:8190
python -m src.tools --list
python -m src.tools get_kpis '{"sites": ["central"], "date_from": "2026-09-25"}'
python -m src.tools get_zone '{"zone_name": "JFK Airport"}'
python -m src.tools get_platform_status
```

## API del agente

`src/api/main.py` (P3-11) es la única puerta de entrada al agente:

```bash
# Desde parte3_agente_conversacional/, con el .env cargado y el coordinador
# (o el mock) en COORDINATOR_URLS
uvicorn src.api.main:app --port 8300
```

| Endpoint | Token (`X-API-Key`) | Qué hace |
|---|---|---|
| `POST /chat` | sí | Pregunta → `ChatResponse` (texto, bloques, fuentes y avisos). 503 si el LLM no responde |
| `GET /status` | sí | Estado de la plataforma (`get_platform_status`), para la barra lateral |
| `GET /health` | no | Comprobación de vida (Docker) |

Con `AGENT_API_TOKEN` vacío no se pide token (modo desarrollo). Cada sesión
recuerda sus últimos `MAX_HISTORY_TURNS` turnos durante una hora.

## Interfaz de chat

`src/ui/app.py` (P3-12) es un chat en Streamlit que solo llama a `POST /chat`
de la API del agente (P3-11): no habla con el coordinador ni con el LLM.

```bash
# Desde parte3_agente_conversacional/, con la API en marcha en AGENT_API_URL
streamlit run src/ui/app.py        # http://localhost:8501
```

- Lee `AGENT_API_URL` y manda `AGENT_API_TOKEN` en la cabecera `X-API-Key`.
- Cada pestaña es una conversación con su `session_id`; «Nueva conversación»
  lo regenera y limpia la pantalla.
- Si la API está parada, el token no es válido o el LLM no responde (503),
  muestra un mensaje claro en lugar de un error de Python.
- `.streamlit/config.toml` oculta el menú de desarrollo de Streamlit.

De cada respuesta pinta todo lo que devuelve `/chat` (P3-13, `src/ui/render.py`):

| Elemento | Cómo se ve |
|---|---|
| Bloque `kpi` | `st.metric` en filas de 3, con unidades ($, millas, viajes) |
| Bloque `table` | `st.dataframe`, unidades en las cabeceras y dos decimales |
| Bloque `line` | `st.line_chart` (los huecos son horas o días ocultos por privacidad) |
| Bloque `bar` | `st.bar_chart` horizontal (sedes, métodos de pago) |
| `warnings` | `st.warning` encima del texto (p. ej. una sede caída) |
| `sources` | Desplegable «Cómo se ha obtenido esta respuesta»: herramienta, argumentos, réplica que respondió, sedes que han respondido y caídas, latencia |

La barra lateral muestra el estado de las sedes, de las réplicas del
coordinador y las fechas con datos (`GET /status`). Se refresca con su
botón y, además, sola cuando una respuesta trae avisos. El saludo incluye
qué puede y qué no puede responder el asistente y cuatro preguntas de
ejemplo que se lanzan con un clic.

Para ver el aviso de sede caída en la demo:

```bash
DOWN_SITES=atocha uvicorn mock.mock_coordinator:app --port 8190
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
