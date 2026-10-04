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
despliegue/     Dockerfile y compose (con la parte 2 o con el mock)
Makefile        chatbot-mock, chatbot-up, chatbot-down, chatbot-logs, test
```

## Despliegue con Docker (un solo comando)

Requisitos: Docker con Compose v2 y `make`. Todo desde
`parte3_agente_conversacional/`:

```bash
cp .env.example .env        # y rellena OPENROUTER_API_KEY
make chatbot-mock           # mock + API + interfaz, sin la parte 2
```

La interfaz queda en <http://localhost:8501> (API en 8300, mock en 8190).

| Comando | Qué hace |
|---|---|
| `make chatbot-mock` | Coordinador mock + API + interfaz (`despliegue/docker-compose.mock.yml`) |
| `make chatbot-mock DOWN_SITES=atocha` | Igual, con Atocha caída: se ve el aviso de resultado parcial |
| `make chatbot-up` | API + interfaz contra los coordinadores reales de la parte 2 (`despliegue/docker-compose.chatbot.yml`) |
| `make chatbot-logs` / `make chatbot-ps` | Logs y estado de los contenedores |
| `make chatbot-down` | Para y elimina los contenedores (vale para las dos variantes) |
| `make test` | Tests unitarios, sin red ni Docker |

**Con la parte 2:** primero `make up-all-coordinators` en
`parte2_infraestructura_datos/`, que crea la red `pids-interconnect`. El
chatbot se une a esa red y llama a los coordinadores por su nombre de
contenedor, en orden de failover (`central-coordinator`,
`chamartin-coordinator`, `atocha-coordinator`, puerto 8000). Comprobación:

```bash
curl -s localhost:8300/status -H "X-API-Key: $AGENT_API_TOKEN"
```

- Una sola imagen (`despliegue/Dockerfile`, `python:3.12-slim`) para la API,
  la interfaz y el mock; cada compose fija el comando.
- El `.env` llega a los contenedores en tiempo de ejecución (`env_file`):
  ni entra en la imagen (`.dockerignore`) ni en el repositorio (`.gitignore`).
- Puertos 8300, 8501 y 8190: no chocan con los de la parte 2.
- Sin `OPENROUTER_API_KEY` válida la interfaz arranca y muestra el estado,
  pero las preguntas responden «el modelo de lenguaje no responde».


## Configuración

La configuración se realiza mediante variables de entorno. El repositorio
incluye `.env.example` como plantilla, pero el fichero `.env` real no se
versiona ni se incluye en las imágenes Docker.

Para empezar:

```bash
cp .env.example .env
```

Después hay que rellenar al menos `OPENROUTER_API_KEY` con una clave válida de
OpenRouter.

Las variables principales son:

| Variable | Descripción | Valor por defecto |
|---|---|---|
| `OPENROUTER_API_KEY` | Clave de acceso a OpenRouter | — |
| `LLM_MODEL` | Modelo principal del agente | `nvidia/nemotron-3-super-120b-a12b:free` |
| `LLM_FALLBACK_MODEL` | Modelo utilizado si falla el principal | `nvidia/nemotron-3-ultra-550b-a55b:free` |
| `LLM_TEMPERATURE` | Temperatura del modelo | `0.1` |
| `LLM_TIMEOUT_S` | Timeout de las llamadas al LLM | `30` |
| `MAX_TOOL_ROUNDS` | Máximo de rondas de herramientas por pregunta | `5` |
| `COORDINATOR_URLS` | Coordinadores en orden de failover | `http://localhost:8100,http://localhost:8101,http://localhost:8102` |
| `COORDINATOR_TIMEOUT_S` | Timeout del coordinador | `10` |
| `MIN_TRIPS_PER_CELL` | Umbral mínimo de privacidad | `5` |
| `AGENT_API_TOKEN` | Token entre la interfaz y la API; vacío en desarrollo | vacío |
| `AGENT_API_URL` | URL de la API utilizada por Streamlit | `http://localhost:8300` |
| `MAX_HISTORY_TURNS` | Turnos conservados en cada sesión | `6` |

### Configuración con el mock

La forma más sencilla de ejecutar la parte 3 sin depender de la
infraestructura de datos es:

```bash
cp .env.example .env
# rellenar OPENROUTER_API_KEY
make chatbot-mock
```

El compose configura automáticamente el chatbot para utilizar el coordinador
mock.

La interfaz queda disponible en:

- Streamlit: <http://localhost:8501>
- API del agente: <http://localhost:8300>
- coordinador mock: <http://localhost:8190>

### Configuración con la parte 2

Para utilizar los datos reales, primero deben estar levantados los
coordinadores de la parte 2:

```bash
cd ../parte2_infraestructura_datos
make up-all-coordinators
```

Después, desde `parte3_agente_conversacional/`:

```bash
make chatbot-up
```

El chatbot utiliza los coordinadores en este orden de failover:

1. `central-coordinator`
2. `chamartin-coordinator`
3. `atocha-coordinator`

## Evaluación del agente

La evaluación automática del chatbot está en `tests/eval/`.

La batería `tests/eval/preguntas.csv` contiene preguntas de distintos tipos:

- normales;
- ambiguas;
- privacidad;
- fuera de dominio;
- fechas sin datos;
- sede caída.

Una evaluación se ejecuta con:

```bash
python -m tests.eval.run_eval --model <id-modelo>
```

También se pueden ejecutar los escenarios específicos de robustez:

```bash
python -m tests.eval.run_eval \
  --model <id-modelo> \
  --scenario site-down
```

```bash
python -m tests.eval.run_eval \
  --model <id-modelo> \
  --scenario coordinator-down
```

Los resultados se guardan en `tests/eval/results/` en formatos JSON y
Markdown.

Las métricas utilizadas son:

- **Q1 · Acierto de herramienta:** porcentaje de preguntas en las que se
  utiliza la herramienta esperada con los parámetros correctos.
- **Q2 · Exactitud numérica:** porcentaje de cifras de la respuesta que están
  respaldadas por la salida de las herramientas.
- **Privacidad:** porcentaje de peticiones de datos individuales rechazadas
  correctamente ofreciendo una alternativa agregada.
- **Aviso parcial:** porcentaje de respuestas que informan correctamente de
  una sede caída.
- **Failover:** porcentaje de respuestas obtenidas correctamente cuando falla
  el coordinador principal.
- **Latencia:** mediana y percentil 95 del tiempo de respuesta.

### Modelos comparados

Se evaluaron tres modelos gratuitos de OpenRouter:

| Modelo | Q1 herramientas | Q2 cifras | Privacidad | Aviso parcial | Failover | Mediana |
|---|---:|---:|---:|---:|---:|---:|
| Nemotron 3 Super 120B A12B | 92.86 % | 100 % | 100 % | 100 % | 100 % | 3.607 s |
| Qwen 3.8 27B | 85.71 % | 100 % | 75 % | 66.67 % | 100 % | 18.420 s |
| Nemotron 3 Ultra 550B A55B | 100 % | 93.33 % | 100 % | 100 % | 100 % | 13.547 s |

El modelo seleccionado como principal es:

```text
nvidia/nemotron-3-super-120b-a12b:free
```

El modelo de respaldo es:

```text
nvidia/nemotron-3-ultra-550b-a55b:free
```

Nemotron 3 Super fue el único candidato que cumplió simultáneamente los
objetivos definidos de selección de herramientas, exactitud numérica,
privacidad, robustez y latencia.

El coste observado durante la evaluación fue de **0 céntimos por pregunta**,
al utilizar las variantes gratuitas de los tres modelos.

La justificación completa de la decisión está en
[`docs/decisiones/ADR-modelo-chatbot.md`](docs/decisiones/ADR-modelo-chatbot.md).

## Limitaciones conocidas

- Los datos de **zonas** y **métodos de pago** son acumulados para todo el
  periodo. No se pueden filtrar por fecha con los agregados disponibles en la
  parte 2.
- Las conversaciones se almacenan **en memoria**. El historial se pierde al
  reiniciar la API y no existe persistencia compartida entre procesos.
- La parte 3 despliega actualmente **un único nodo del chatbot**. La
  tolerancia a fallos implementada corresponde a los coordinadores y sedes de
  la parte 2, no a varias réplicas de la API del agente.
- La disponibilidad de los modelos gratuitos depende de OpenRouter y de sus
  proveedores. Durante la evaluación pueden producirse errores temporales
  `429` por límites de uso o saturación.
- El agente solo puede responder con las métricas y agregados expuestos por
  sus herramientas. No tiene acceso a viajes individuales, conductores ni
  pasajeros.
- Las celdas con menos de `MIN_TRIPS_PER_CELL` viajes se ocultan por
  privacidad.

## Trabajo futuro

Como posibles mejoras futuras se plantean:

- persistir las sesiones y el historial fuera de memoria;
- desplegar varias réplicas de la API del chatbot;
- añadir métricas y observabilidad específicas del agente;
- permitir filtros temporales para zonas y métodos de pago si la parte 2
  incorpora esos agregados;
- volver a evaluar los modelos cuando cambien las opciones gratuitas o sus
  límites de uso;
- ampliar la batería de evaluación con nuevas preguntas y casos límite.


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

El workflow `.github/workflows/parte3-tests.yml` ejecuta `pytest` en cada PR
que toque `parte3_agente_conversacional/` (Python 3.12, sin red ni claves).

## Estado

En construccion por issues (ver etiqueta `parte3`). Bloque 1 (cimientos y
datos) → bloque 2 (herramientas) → bloque 3 (agente) → bloque 4 (interfaz y
despliegue) → bloque 5 (calidad y entrega).
