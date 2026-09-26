# Parte 2 · Infraestructura de captura y análisis de datos

Prueba de concepto de una plataforma de datos para la startup de VTC/taxi,
diseñada bajo la restricción **E2 · Despliegue distribuido**: los viajes se
generan en tres sedes (**Central**, **Chamartín** y **Atocha**), cada sede
conserva sus datos y **ningún registro crudo sale de ella**. Las preguntas
que necesitan datos de varias sedes se responden combinando agregados.

| Documento | Para qué |
|---|---|
| Este README | Qué es, cómo se ejecuta, cómo se consulta y cómo se prueba |
| [`ARQUITECTURA.md`](ARQUITECTURA.md) | Cómo está montado por dentro, fichero a fichero |
| [`COMPARATIVA.md`](COMPARATIVA.md) | Por qué cada tecnología y cómo cambiaría con E3, E4 y E8 |
| [`tests/results/`](tests/results/) | Resultados medidos de las métricas M1, M2 y M3 |

---

## Índice

1. [Visión general](#1-visión-general)
2. [Requisitos](#2-requisitos)
3. [Puesta en marcha paso a paso](#3-puesta-en-marcha-paso-a-paso)
4. [Operación del despliegue](#4-operación-del-despliegue)
5. [Consultar los datos](#5-consultar-los-datos)
6. [Tests y métricas de calidad](#6-tests-y-métricas-de-calidad)
7. [Estructura del directorio](#7-estructura-del-directorio)
8. [Datos y esquema canónico](#8-datos-y-esquema-canónico)
9. [Limitaciones conocidas](#9-limitaciones-conocidas)
10. [Solución de problemas](#10-solución-de-problemas)

---

## 1. Visión general

```
                 ┌──────────── cada sede (x3) ─────────────┐
 CSV histórico ──┼─► batch_bronze ─┐                        │
                 │                 ├─► Bronze ─► Silver ─► Gold (Postgres) ─► site_api ─┐
 CSV realtime ───┼─► producer ─► Kafka ─► stream_bronze ─┘      (cuarentena)            │
                 └─────────────────────────────────────────────────────────┘            │
                                                                                        ▼
                     coordinador (replicado en las 3 sedes) ◄── solo conteos y sumas ───┘
                                     │
                                     ▼
                     cliente / chatbot (failover Central → Chamartín → Atocha)
```

- **Dentro de cada sede:** Kafka, Spark (Bronze → Silver → Gold, arquitectura
  medallion), Postgres y la `site_api`. El histórico entra en lote y el
  tiempo real por Kafka; los dos pasan por las mismas reglas de calidad.
- **Lo único que sale de una sede:** conteos y sumas por hora, día, zona y
  método de pago, a través de su `site_api`.
- **El coordinador** pide esos agregados a las tres sedes, los suma y
  calcula las medias una sola vez. Está replicado en las tres sedes; si una
  sede cae, responde con las otras dos e indica `partial: true`.

| Tecnología | Uso |
|---|---|
| Python + pandas | Preparación de datos y simulación de tiempo real |
| Apache Kafka 3.8 (KRaft) | Bus de eventos, un broker por sede |
| Apache Spark 4.2 (PySpark) | Procesamiento batch y streaming |
| Parquet | Lakehouse (Bronze, Silver, cuarentena) en un volumen por sede |
| PostgreSQL 16 | Agregados Gold por sede |
| FastAPI | `site_api` de cada sede y coordinador |
| Docker Compose + Makefile | Despliegue de las tres sedes |
| Prometheus + Grafana | Monitorización (nodo central) |
| pytest | Tests y métricas de calidad |

---

## 2. Requisitos

| Requisito | Versión / detalle |
|---|---|
| Docker Engine + Docker Compose v2 | `docker compose version` debe responder |
| `make` | Para los comandos del Makefile |
| Python | **3.11 o superior** (recomendado 3.12): lo exigen pandas 3 y numpy 2.5 |
| Memoria | Unos **10 GB libres** para las tres sedes completas (9 procesos Spark + 3 Kafka + 3 Postgres) |
| Dataset | `data/raw/rows.csv` (muestra del NYC Yellow Taxi 2020 de Moodle). No se versiona |

**Windows:** todo se ejecuta desde **WSL 2** (Ubuntu), con Docker Engine
instalado dentro de WSL o con Docker Desktop y su integración con WSL. Para
dar memoria suficiente a WSL, crea `C:\Users\<usuario>\.wslconfig`:

```ini
[wsl2]
memory=10GB
swap=8GB
```

y aplica con `wsl --shutdown` desde PowerShell.

**Puertos que se publican en el host:**

| Servicio | Central | Chamartín | Atocha |
|---|---|---|---|
| `site_api` | 8000 | 8001 | 8002 |
| Coordinador | 8100 | 8101 | 8102 |
| Postgres | 5432 | 5433 | 5434 |
| Métricas del producer | 9000 | 9001 | 9002 |
| Prometheus / Grafana (compose central) | 9090 / 3000 | — | — |

---

## 3. Puesta en marcha paso a paso

Todos los comandos se ejecutan **desde `parte2_infraestructura_datos/`**.

**1. Entorno de Python** (fuera de la carpeta del repo)

```bash
python3 -m venv ~/.venvs/pids          # o: uv venv --python 3.12 ~/.venvs/pids
source ~/.venvs/pids/bin/activate
pip install -r requirements-dev.txt    # requirements.txt + pytest
```

**2. Datos**

Copia `rows.csv` en `data/raw/` y prepara los ficheros de cada sede:

```bash
python -m scripts.prepare_data
```

Genera `data/prepared/<sede>/historical.csv` y `realtime.csv` y valida el
resultado (filas conservadas, sedes y fuentes válidas, `trip_id` únicos).

**3. Levantar las tres sedes**

```bash
make up-all-coordinators
```

La primera vez construye las imágenes (varios minutos). Cada sede arranca
Kafka, Postgres, el producer, los jobs de Spark, la `site_api` y su
coordinador. `spark_batch_bronze` carga el histórico una vez y termina
(`Exited (0)` es su estado normal).

**4. Comprobar que funciona** (espera 5–8 minutos a que se procesen los datos)

```bash
docker ps -a --format "table {{.Names}}\t{{.Status}}"
curl -s localhost:8000/health                      # site_api de Central
make failover-check                                # responde el coordinador de Central

# Total de viajes en Gold: repetir hasta que deje de cambiar
curl -s localhost:8100/metrics/payment | python3 -c \
  "import sys,json; print(sum(r['trip_count'] for r in json.load(sys.stdin)['data']))"
```

Con la muestra de Moodle el total final es **994**: los 999 viajes menos
1 en cuarentena y 4 cancelados.

**5. (Opcional) Liberar memoria**

Cuando Gold está cargado, Kafka, el producer y Spark ya no hacen falta para
consultar. Pararlos libera unos 7 GB y los datos siguen en Postgres:

```bash
for s in central chamartin atocha; do
  docker compose -p $s --env-file sites/$s.env -f deploy/docker-compose.site.yml \
    stop producer kafka spark_stream_bronze spark_silver spark_sink_postgres
done
```

---

## 4. Operación del despliegue

### Comandos del Makefile

`SITE` puede ser `central`, `chamartin` o `atocha`.

| Comando | Qué hace |
|---|---|
| `make up-all-coordinators` | Levanta las tres sedes con su coordinador |
| `make up-coordinator SITE=<sede>` | Levanta una sede con su coordinador |
| `make up SITE=<sede>` | Levanta una sede sin coordinador |
| `make stop-coordinator SITE=<sede>` | Para solo el coordinador de esa sede (demo de failover) |
| `make failover-check [FAILOVER_PATH=/metrics/daily]` | Consulta el coordinador con failover y dice qué réplica respondió |
| `make ps` / `make logs` `SITE=<sede>` | Estado y logs de una sede |
| `make build SITE=<sede>` | Reconstruye las imágenes |
| `make down SITE=<sede>` / `make down-all` | Para y elimina los contenedores (conserva los datos) |
| `make clean SITE=<sede>` | Para y **borra** los datos de la sede (Postgres, lakehouse, checkpoints) |

`make up` reconstruye las imágenes si ha cambiado el código de `src/`
(`--build`), así que no hace falta un `make build` previo.

> ⚠️ **No relances `make up` sobre una sede que ya tiene datos.** Vuelve a
> arrancar el producer, que publica de nuevo todo el tiempo real, y esos
> viajes se contarían dos veces en Gold. Para empezar de cero:
>
> ```bash
> for s in central chamartin atocha; do make clean SITE=$s; done
> make up-all-coordinators
> ```

### Despliegue ligero (sin Spark ni Kafka)

Para probar solo las APIs, el coordinador o el failover (por ejemplo, el test
M1) basta con Postgres, `site_api` y coordinador. Las respuestas vendrán
vacías porque no hay pipeline:

```bash
make network
for s in central chamartin atocha; do
  docker compose -p $s --env-file sites/$s.env -f deploy/docker-compose.site.yml \
    --profile coordinator up -d --build postgres site_api coordinator
done
```

### Sedes en máquinas distintas

Cada sede puede ejecutarse en su propia máquina con el mismo compose. En el
`.env` de cada sede hay que apuntar el coordinador a las APIs remotas con
`SITE_API_URL_CENTRAL`, `SITE_API_URL_CHAMARTIN` y `SITE_API_URL_ATOCHA`
(ver `sites/.env.example`), y en el cliente fijar `COORDINATOR_URLS`.

### Monitorización

```bash
docker compose -f deploy/docker-compose.central.yml up -d
```

- Prometheus: <http://localhost:9090> · Grafana: <http://localhost:3000> (`admin` / `admin`)
- Dashboards autoprovisionados: **negocio** y **operacional**
  (`monitoring/grafana/provisioning/dashboards/`).
- Se recogen métricas de la `site_api` (`/prometheus`) y del producer de cada sede.
- Con Docker Engine en Linux/WSL (sin Docker Desktop), `host.docker.internal`
  no existe: añade `extra_hosts: ["host.docker.internal:host-gateway"]` al
  servicio `prometheus` de `docker-compose.central.yml`.

---

## 5. Consultar los datos

### API de cada sede (`site_api`)

Solo devuelve **agregados combinables** (conteos y sumas), nunca viajes
individuales ni medias.

| Endpoint | Filtros | Devuelve |
|---|---|---|
| `GET /health` | — | Estado y sede |
| `GET /metrics/hourly` | `date_from`, `date_to` | Agregados por hora de recogida |
| `GET /metrics/daily` | `date_from`, `date_to` | Agregados por día |
| `GET /metrics/zone` | `pu_location_id` | Agregados por zona de recogida |
| `GET /metrics/payment` | `payment_type` | Agregados por método de pago |
| `GET /quarantine/summary` | `date_from`, `date_to` | Filas rechazadas por motivo |
| `GET /prometheus` | — | Métricas técnicas para Prometheus |

Cada fila lleva `trip_count`, `sum_fare_amount`, `sum_trip_distance`,
`sum_tip_amount` y `sum_total_amount`. La documentación interactiva está en
`http://localhost:800X/docs`.

### Coordinador

Mismos endpoints `/metrics/*` que la `site_api`, pero combinando las tres
sedes y añadiendo las medias (`avg_*` = Σ sumas / Σ conteos):

```bash
curl -s "localhost:8100/metrics/daily" | python3 -m json.tool
```

```json
{
  "sites_ok": ["atocha", "central", "chamartin"],
  "sites_failed": [],
  "partial": false,
  "data": [{"trip_date": "2020-01-01", "trip_count": "...", "sum_fare_amount": "...", "avg_fare_amount": "...", "...": "..."}]
}
```

- `partial: true` y `sites_failed` indican que faltan sedes: los totales
  solo incluyen las sedes en `sites_ok`.
- Con las tres sedes caídas responde `200` con `sites_ok: []` y sin datos:
  **el cliente debe mirar `sites_ok` / `partial`**, no solo el código HTTP.
- Las medias llegan con muchos decimales: conviene redondearlas al mostrarlas.

### Coordinador replicado y failover

El coordinador no guarda estado, así que hay una copia idéntica en cada
sede. Las réplicas no se conocen entre sí: **el failover lo hace quien
consume el coordinador** (por ejemplo, el agente conversacional de la
parte 3), en este orden:

| Prioridad | Réplica | URL |
|---|---|---|
| 1º | Central | `http://localhost:8100` |
| 2º | Chamartín | `http://localhost:8101` |
| 3º | Atocha | `http://localhost:8102` |

Reglas para el cliente (implementación de referencia en
`scripts/coordinator_failover.py`):

1. Llamar a la réplica de mayor prioridad.
2. Si no se puede conectar, hay timeout o devuelve un `5xx`, pasar a la
   siguiente.
3. Si devuelve un `4xx`, no reintentar en las demás: todas ejecutan el
   mismo código y fallarían igual.
4. Si ninguna responde, informar del error.
5. El timeout del cliente debe ser **mayor** que el que usa el
   coordinador con cada sede (`SITE_API_TIMEOUT_SECONDS`, 5 s por
   defecto). Si una sede se queda colgada, el coordinador tarda ese
   tiempo en devolver la respuesta parcial; un cliente con el mismo
   timeout la descartaría y saltaría a otra réplica que tarda lo mismo,
   de modo que una sola sede colgada tumbaría todo el servicio. El
   cliente de referencia usa 10 s (`COORDINATOR_TIMEOUT_SECONDS`).

Las URLs se cambian con `COORDINATOR_URLS` (separadas por comas, en orden de
failover). `GET /health` indica qué réplica responde:
`{"status": "ok", "site_id": "chamartin", "failover_priority": 2}`.

**Demo:** parar el coordinador de Central y comprobar que responde Chamartín.

```bash
make failover-check                  # Answered by: http://localhost:8100 ... "central"
make stop-coordinator SITE=central
make failover-check                  # Skipped: http://localhost:8100: ConnectError
                                     # Answered by: http://localhost:8101 ... "chamartin"
make failover-check FAILOVER_PATH=/metrics/daily   # los datos siguen llegando
make up-coordinator SITE=central     # volver a levantarlo
```

---

## 6. Tests y métricas de calidad

```bash
pytest                         # tests sin Docker (~2 s)
pytest --integration           # además, contra el despliegue en marcha
pytest --integration -k m2     # solo una métrica
```

- Los tests **sin Docker** simulan las sedes y validan el contrato de las
  APIs, el coordinador, el failover y la referencia de M3.
- Los tests **de integración** necesitan las tres sedes levantadas y con
  datos (paso 3). **M1 para y congela contenedores**: no lo lances sobre un
  despliegue que estés usando para otra cosa.
- El test que cruza la referencia de M3 con Spark se salta si no hay Java.
- Cada métrica escribe sus cifras en `tests/results/<métrica>.md` y `.json`.

Las tres métricas propias de la restricción E2:

| Métrica | Pregunta | Resultado medido | Detalle |
|---|---|---|---|
| **M1 · Disponibilidad** | ¿Se responde si cae una sede? | **100 %** de consultas respondidas en los 8 escenarios con al menos una sede viva (API caída, API colgada, sede entera caída, dos sedes caídas); 100 % de sedes caídas bien señaladas | [`m1_availability.md`](tests/results/m1_availability.md) |
| **M2 · Transferencia de crudos** | ¿Sale algún dato crudo de una sede? | **0 bytes** crudos y 0 `trip_id` en todas las respuestas; lo que sale ocupa un 6 % del crudo de la sede | [`m2_transfer.md`](tests/results/m2_transfer.md) |
| **M3 · Exactitud** | ¿La respuesta unificada es correcta? | **0 diferencias** frente a un cálculo centralizado de los 994 viajes; la "media de medias" habría errado hasta un 48 % | [`m3_accuracy.md`](tests/results/m3_accuracy.md) |

`m1_availability_antes_fix.md` conserva el resultado de M1 antes de
corregir el timeout del cliente de failover (0 % de disponibilidad con una
sede colgada).

---

## 7. Estructura del directorio

```
parte2_infraestructura_datos/
├── README.md                  # este documento
├── ARQUITECTURA.md            # arquitectura detallada, fichero a fichero
├── COMPARATIVA.md             # alternativas evaluadas y adaptación a E3/E4/E8
├── Makefile                   # despliegue por sede
├── requirements.txt           # dependencias de las imágenes
├── requirements-dev.txt       # + pytest
├── pytest.ini
├── data/
│   ├── raw/                   # rows.csv (no versionado)
│   └── prepared/<sede>/       # historical.csv y realtime.csv (generados)
├── scripts/
│   ├── prepare_data.py        # reparto por sede + separación 80/20
│   └── coordinator_failover.py# cliente de referencia con failover
├── src/
│   ├── common/                # schema.py (esquema canónico), cleaning.py (reglas de calidad)
│   ├── producer/              # simulador de tiempo real → Kafka
│   ├── spark_jobs/            # batch_bronze, stream_bronze, silver, gold, sink_postgres
│   ├── site_api/              # API de cada sede
│   └── coordinator/           # coordinador (main.py) y clientes HTTP (clients.py)
├── sql/                       # init.sql (tablas Gold), quarantine.sql
├── deploy/
│   ├── docker-compose.site.yml    # plantilla de una sede
│   └── docker-compose.central.yml # Prometheus + Grafana
├── sites/                     # central.env, chamartin.env, atocha.env, .env.example
├── monitoring/                # prometheus.yml y provisioning de Grafana
└── tests/
    ├── conftest.py            # configuración común y opción --integration
    ├── test_m1_availability.py
    ├── test_m2_transfer.py
    ├── test_m3_accuracy.py
    └── results/               # cifras medidas de cada métrica
```

---

## 8. Datos y esquema canónico

Esta sección documenta la preparación de los datos y el esquema canónico
utilizado por los componentes de la plataforma.

### Dataset de entrada

El dataset original contiene 18 campos correspondientes a viajes de taxi:

- `VendorID`
- `tpep_pickup_datetime`
- `tpep_dropoff_datetime`
- `passenger_count`
- `trip_distance`
- `RatecodeID`
- `store_and_fwd_flag`
- `PULocationID`
- `DOLocationID`
- `payment_type`
- `fare_amount`
- `extra`
- `mta_tax`
- `tip_amount`
- `tolls_amount`
- `improvement_surcharge`
- `total_amount`
- `congestion_surcharge`

El fichero original se almacena en:

`data/raw/`

y no se modifica durante la preparación.

---

### Esquema canónico

Todos los componentes de la plataforma utilizan un esquema canónico común
definido en:

`src/common/schema.py`

Los nombres originales del CSV se normalizan a `snake_case`.

| Campo original | Campo canónico |
|---|---|
| `VendorID` | `vendor_id` |
| `tpep_pickup_datetime` | `pickup_datetime` |
| `tpep_dropoff_datetime` | `dropoff_datetime` |
| `passenger_count` | `passenger_count` |
| `trip_distance` | `trip_distance` |
| `RatecodeID` | `ratecode_id` |
| `store_and_fwd_flag` | `store_and_fwd_flag` |
| `PULocationID` | `pu_location_id` |
| `DOLocationID` | `do_location_id` |
| `payment_type` | `payment_type` |
| `fare_amount` | `fare_amount` |
| `extra` | `extra` |
| `mta_tax` | `mta_tax` |
| `tip_amount` | `tip_amount` |
| `tolls_amount` | `tolls_amount` |
| `improvement_surcharge` | `improvement_surcharge` |
| `total_amount` | `total_amount` |
| `congestion_surcharge` | `congestion_surcharge` |

Además de los campos originales, el esquema incorpora los siguientes
metadatos:

| Campo | Tipo | Descripción |
|---|---|---|
| `trip_id` | string | Identificador determinista del viaje |
| `site_id` | string | Sede propietaria del registro |
| `source` | string | Origen del procesamiento: `historical` o `realtime` |
| `schema_version` | integer | Versión del esquema canónico |
| `ingest_ts` | timestamp | Instante en el que el registro entra al pipeline |

La versión inicial del esquema es:

`schema_version = 1`

Los posibles valores de `site_id` son:

- `central`
- `chamartin`
- `atocha`

Los posibles valores de `source` son:

- `historical`
- `realtime`

Los campos monetarios utilizan `DecimalType(12, 2)` para evitar los
problemas de precisión asociados a la representación de cantidades
monetarias mediante números de coma flotante.

---

### Identificador de viaje

El dataset original no proporciona un identificador único de viaje.

Por este motivo se genera `trip_id` mediante SHA-256 a partir de una
representación canónica de los 18 campos originales del viaje.

Los metadatos añadidos por la plataforma (`site_id`, `source`,
`schema_version` e `ingest_ts`) no forman parte del cálculo.

El identificador se genera durante la preparación de los datos y no se
vuelve a calcular posteriormente.

Esto permite que un viaje conserve su identidad aunque sus timestamps
sean desplazados durante la simulación realtime.

---

### Distribución entre sedes

El escenario distribuido utiliza tres sedes:

- Central
- Chamartín
- Atocha

Cada registro pertenece exclusivamente a una sede.

La asignación se realiza de forma determinista utilizando
`PULocationID`:

| `PULocationID % 3` | Sede |
|---|---|
| `0` | `central` |
| `1` | `chamartin` |
| `2` | `atocha` |

Esta partición es una decisión técnica para distribuir los datos del
dataset entre las tres sedes. No representa una correspondencia
geográfica entre las zonas del dataset y las sedes.

La principal propiedad de este criterio es que todos los viajes con el
mismo `PULocationID` pertenecen siempre a la misma sede.

---

### Separación historical/realtime

Una vez asignados los registros a una sede, los viajes de cada sede se
ordenan cronológicamente por `pickup_datetime`.

Los datos se dividen de la siguiente forma:

- Primer 80 %: `historical`
- Último 20 %: `realtime`

De esta manera, el conjunto realtime representa temporalmente el tramo
posterior de los datos de cada sede.

Los ficheros generados se almacenan con la siguiente estructura:

```
data/prepared/
├── central/
│   ├── historical.csv
│   └── realtime.csv
├── chamartin/
│   ├── historical.csv
│   └── realtime.csv
└── atocha/
    ├── historical.csv
    └── realtime.csv
```

La preparación se realiza mediante:

`python3 -m scripts.prepare_data`

El script comprueba al finalizar:

- conservación del número total de registros;
- validez de `site_id`;
- validez de `source`;
- existencia de `trip_id`;
- asignación de cada `PULocationID` a una única sede;
- posibles identificadores duplicados.

---

### Simulación de datos realtime

Cada sede dispone de un producer que lee su fichero `realtime.csv` y
publica los viajes en Kafka.

El producer está implementado en:

`src/producer/producer.py`

Al iniciar la simulación se calcula un desplazamiento temporal entre el
primer `pickup_datetime` del dataset realtime y el instante actual.

Ese mismo desplazamiento se aplica a `pickup_datetime` y
`dropoff_datetime`, conservando la duración original de cada viaje.

El `trip_id` no se recalcula después de modificar los timestamps.

La velocidad de reproducción es configurable mediante
`ACCELERATION_FACTOR`. Por ejemplo, con:

`ACCELERATION_FACTOR=60`

60 segundos de tiempo en el dataset se reproducen en 1 segundo real.

El producer se configura mediante variables de entorno:

- `SITE_ID`
- `REALTIME_FILE`
- `KAFKA_BOOTSTRAP_SERVERS`
- `KAFKA_TOPIC`
- `ACCELERATION_FACTOR`

Esto permite utilizar el mismo código del producer en las tres sedes.

---

### `ingest_ts`

`ingest_ts` no se genera durante `prepare_data.py` ni durante la
simulación del producer.

Representa el instante en el que un registro entra realmente en el
pipeline de procesamiento.

Por tanto, será asignado por el proceso de entrada a Bronze tanto para
el flujo histórico como para el flujo realtime.

---

## 9. Limitaciones conocidas

| Tema | Detalle |
|---|---|
| **Reejecutar el producer duplica el tiempo real** | `make up` sobre una sede con datos relanza el producer y vuelve a publicar todo el realtime. La deduplicación por `trip_id` solo actúa dentro de cada micro-batch, así que Gold lo cuenta dos veces. Hasta corregirlo, reiniciar siempre con `make clean` |
| **Postgres publica su puerto en el host** | 5432–5434 con credenciales de desarrollo; `silver_rejected` puede guardar viajes completos. Es la única vía de salida de datos no agregados (M2 la marca como fallo conocido) |
| **La cuarentena no llega a Postgres** | Silver escribe la cuarentena en Parquet y ningún job la vuelca a `silver_rejected`: `/quarantine/summary` devuelve `[]` |
| **Coordinador sin métricas de Prometheus** | Solo la `site_api` y el producer exponen métricas |
| **Credenciales de desarrollo** | `pids/pids` en Postgres y `admin/admin` en Grafana |
| **Consumo de memoria** | Cada job de Spark es una JVM de ~0,7 GB: las tres sedes completas ocupan unos 8–9 GB |
| **Parquet sin formato transaccional** | Sin Delta Lake ni Iceberg, la idempotencia se garantiza a mano (checkpoints, `processed_batches`, carga única del histórico) |
| **Dataset de muestra** | 999 viajes; con el dataset completo de NYC habría que revisar particionado y recursos |

Las propuestas de mejora y la adaptación a otras restricciones están en
[`COMPARATIVA.md`](COMPARATIVA.md).

---

## 10. Solución de problemas

| Síntoma | Causa probable y solución |
|---|---|
| `openjdk-17-jre-headless has no installation candidate` al construir | Imagen de Spark sin fijar a Debian 12. Ya corregido en `src/spark_jobs/Dockerfile` (`python:3.12-slim-bookworm`); actualiza la rama |
| Gold se queda en 198 viajes | No ha entrado el histórico: comprueba `docker logs <sede>-spark-batch-bronze` (debe terminar con `Exited (0)`) |
| Gold se queda en 796 viajes | No ha entrado el tiempo real: `docker logs <sede>-spark-silver` y `docker logs <sede>-spark-stream-bronze` |
| Gold supera 994 viajes | Se relanzó el producer sobre una sede con datos: `make clean` en las tres sedes y volver a levantar |
| Un cambio en `src/` no se refleja | Imagen antigua: `make build SITE=<sede>` (o `make up`, que ya reconstruye) |
| Contenedores `unhealthy` o reinicios en bucle | Falta memoria: sube `memory` en `.wslconfig` o libera memoria parando Spark/Kafka tras la carga |
| `port is already allocated` en 5432 | Hay otro Postgres en el equipo: páralo o cambia `POSTGRES_PORT` en `sites/<sede>.env` |
| `Cannot connect to the Docker daemon` (WSL) | `sudo systemctl start docker` (o `sudo service docker start`) |
| `permission denied ... docker.sock` | Añade tu usuario al grupo: `sudo usermod -aG docker $USER` y reinicia WSL |
| `make: python: not found` | Activa el entorno virtual (`source ~/.venvs/pids/bin/activate`) |
| Tests de integración en `skipped` | Alguna `/health` no responde: revisa el paso 4 de la puesta en marcha |
