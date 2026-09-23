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
