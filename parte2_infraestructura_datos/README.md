# Preparación de datos y esquema canónico

Esta sección documenta la preparación de los datos y el esquema canónico
utilizado por los componentes de la plataforma.

## Dataset de entrada

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

## Esquema canónico

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

## Identificador de viaje

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

## Distribución entre sedes

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

## Separación historical/realtime

Una vez asignados los registros a una sede, los viajes de cada sede se
ordenan cronológicamente por `pickup_datetime`.

Los datos se dividen de la siguiente forma:

- Primer 80 %: `historical`
- Último 20 %: `realtime`

De esta manera, el conjunto realtime representa temporalmente el tramo
posterior de los datos de cada sede.

Los ficheros generados se almacenan con la siguiente estructura:

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

## Simulación de datos realtime

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

## `ingest_ts`

`ingest_ts` no se genera durante `prepare_data.py` ni durante la
simulación del producer.

Representa el instante en el que un registro entra realmente en el
pipeline de procesamiento.

Por tanto, será asignado por el proceso de entrada a Bronze tanto para
el flujo histórico como para el flujo realtime.

---

## Coordinador replicado y failover

El coordinador (`src/coordinator/`) consulta las tres `site_api`, suma
sus agregados combinables y calcula las medias una sola vez. Es
**stateless**: no guarda nada entre peticiones. Por eso se puede replicar
tal cual en las tres sedes sin sincronizar nada entre las instancias.

### Despliegue

El coordinador es un servicio opcional de `deploy/docker-compose.site.yml`
bajo el profile `coordinator`, y se puede activar de forma independiente
en cualquier sede:

```bash
make up-coordinator SITE=central     # primario
make up-coordinator SITE=chamartin   # respaldo 1
make up-coordinator SITE=atocha      # respaldo 2
make up-all-coordinators             # las tres de una vez
```

Sin el profile (`make up`), la sede se levanta sin coordinador.

Cada réplica tiene que llegar a las APIs de las tres sedes, no solo a la
suya. Para eso, `site_api` y `coordinator` se unen a una red docker
compartida, `pids-interconnect`, que el Makefile crea automáticamente
(`make network`). Dentro de esa red, cada API es accesible como
`http://site-api-<sede>:8000`. Si las sedes se despliegan en máquinas
distintas, las URLs se sobreescriben con `SITE_API_URL_CENTRAL`,
`SITE_API_URL_CHAMARTIN` y `SITE_API_URL_ATOCHA` (ver
`sites/.env.example`).

### Orden de failover

| Prioridad | Sede | Rol | URL (host) |
|---|---|---|---|
| 1º | `central` | primario | `http://localhost:8100` |
| 2º | `chamartin` | respaldo | `http://localhost:8101` |
| 3º | `atocha` | respaldo | `http://localhost:8102` |

Las réplicas no se conocen entre sí, así que **el failover lo hace quien
consume el coordinador** (por ejemplo, el agente conversacional, #66):

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

La implementación de referencia está en `scripts/coordinator_failover.py`.
Las URLs se pueden cambiar con `COORDINATOR_URLS` (lista separada por
comas, **en orden de failover**).

`GET /health` de cada réplica indica qué réplica ha respondido:

```json
{"status": "ok", "site_id": "chamartin", "failover_priority": 2}
```

No hay que confundir esto con la **degradación parcial**, que es algo
distinto: si una *sede* (su `site_api`) está caída, cualquier réplica del
coordinador sigue respondiendo con las otras dos y lo indica con
`partial: true` y `sites_failed`.

### Demo: parar Central y comprobar que responde Chamartín

```bash
make up-all-coordinators
make failover-check                  # Answered by: http://localhost:8100 ... "site_id": "central"

make stop-coordinator SITE=central
make failover-check                  # Skipped: http://localhost:8100: ConnectError
                                     # Answered by: http://localhost:8101 ... "site_id": "chamartin"

make failover-check FAILOVER_PATH=/metrics/daily   # los datos siguen llegando
```
