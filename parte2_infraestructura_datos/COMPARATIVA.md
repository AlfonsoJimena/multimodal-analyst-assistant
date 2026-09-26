# Comparativa de alternativas y adaptación a otras restricciones — Parte 2

Documento de la issue #69. Justifica por qué se eligió cada tecnología de
la plataforma frente a sus alternativas, siempre desde la restricción que
nos tocó (**E2 · Despliegue distribuido**), y explica cómo cambiaría el
diseño con otras restricciones del enunciado (**E3, E4 y E8**).

Complementa a [`ARQUITECTURA.md`](ARQUITECTURA.md) (cómo está montado) y a
los resultados de las métricas en [`tests/results/`](tests/results/).

---

## Índice

1. [La restricción E2 y los criterios de comparación](#1-la-restricción-e2-y-los-criterios-de-comparación)
2. [Resumen de decisiones](#2-resumen-de-decisiones)
3. [Comparativa por capa](#3-comparativa-por-capa)
   - [3.1 Ingesta](#31-ingesta)
   - [3.2 Procesamiento](#32-procesamiento)
   - [3.3 Lakehouse (Bronze / Silver)](#33-lakehouse-bronze--silver)
   - [3.4 Serving (Gold + API de sede)](#34-serving-gold--api-de-sede)
   - [3.5 Consulta unificada](#35-consulta-unificada)
   - [3.6 Despliegue](#36-despliegue)
4. [Qué validaron las métricas](#4-qué-validaron-las-métricas)
5. [Adaptación a otras restricciones](#5-adaptación-a-otras-restricciones)
   - [5.1 E3 · Privacidad total](#51-e3--privacidad-total)
   - [5.2 E4 · Varios consumidores](#52-e4--varios-consumidores)
   - [5.3 E8 · Retención y ciclo de vida](#53-e8--retención-y-ciclo-de-vida-de-los-datos)
   - [5.4 Resumen del esfuerzo de adaptación](#54-resumen-del-esfuerzo-de-adaptación)

---

## 1. La restricción E2 y los criterios de comparación

El enunciado de E2 pide:

> Los datos se generan en 3 ubicaciones físicas distintas (oficina central,
> Chamartín, estación de Atocha). Cada ubicación mantiene sus propios datos y
> no puede centralizar los registros crudos.

y concreta cuatro exigencias:

| # | Exigencia de E2 | Dónde la resolvemos |
|---|---|---|
| E2.1 | Definir qué se replica, qué se agrega localmente y qué se consulta a distancia | §3.5 |
| E2.2 | Especificar el comportamiento si una ubicación no está disponible | §3.5, métrica M1 |
| E2.3 | Las respuestas del chatbot pueden requerir datos de varias ubicaciones | §3.5, métrica M3 |
| E2.4 | Responder consultas unificadas sin transferir innecesariamente datos crudos | §3.4, métrica M2 |

De ahí salen los criterios con los que se ha comparado cada capa:

| Criterio | Qué significa |
|---|---|
| **C1 · Soberanía del dato** | Los registros crudos no salen de su sede, ni siquiera por diseño accidental (puertos, redes compartidas). |
| **C2 · Tolerancia a la caída de una sede** | Una sede caída o lenta no tumba el servicio de las demás. |
| **C3 · Exactitud de la respuesta unificada** | Combinar tres sedes da exactamente lo mismo que un cálculo centralizado. |
| **C4 · Mismo código para histórico y tiempo real** | Las reglas de calidad no pueden divergir entre batch y streaming. |
| **C5 · Coste de operación en la PdC** | Las tres sedes corren en un portátil del equipo (WSL, ~10 GB de RAM). |
| **C6 · Madurez y ecosistema** | Documentación, conectores entre piezas, uso en industria y en la asignatura. |

---

## 2. Resumen de decisiones

| Capa | Elección | Alternativa principal descartada | Motivo decisivo (criterio) |
|---|---|---|---|
| Ingesta | Apache Kafka (KRaft), **un broker por sede** | Kafka/RabbitMQ central compartido | Un bus central recibiría todos los eventos crudos (C1) |
| Procesamiento | Apache Spark 4.2 (PySpark), batch + Structured Streaming | Apache Flink | Misma API y mismas reglas para batch y streaming (C4, C6) |
| Lakehouse | Parquet particionado en volumen local de cada sede (medallion) | Delta Lake / Iceberg | Simplicidad de la PdC (C5); se documenta como mejora |
| Serving | PostgreSQL por sede con agregados combinables + `site_api` (FastAPI) como única salida | Exponer la BD de la sede por SQL | La API decide qué sale; solo conteos y sumas (C1, C3) |
| Consulta unificada | Coordinador sin estado, replicado en las 3 sedes, failover en el cliente | Motor federado (Trino) o replicar Gold a una BD central | Nada crudo viaja, sin punto único de fallo (C1, C2, C3) |
| Despliegue | Docker Compose: una plantilla + un `.env` por sede, red compartida solo para APIs | Kubernetes | Aislamiento suficiente con coste mínimo en una máquina (C5) |

---

## 3. Comparativa por capa

Leyenda de la columna "Encaje con E2": ✅ encaja · ⚠️ encaja con reservas · ❌ la incumple.

### 3.1 Ingesta

Cómo entran los viajes en tiempo real a cada sede. El histórico no pasa
por aquí: se carga en lote desde CSV (`batch_bronze.py`).

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **Kafka, un broker por sede (elegida)** | Log persistente y re-legible por offset; integración nativa con Spark Structured Streaming (checkpoints por offset); varios consumidores independientes; modo KRaft sin ZooKeeper | JVM pesada; un broker de un nodo no es tolerante a fallos dentro de la sede | ✅ Los eventos crudos no salen de la sede |
| Kafka central compartido por las 3 sedes | Un único clúster que operar; replicación entre brokers | Todos los viajes crudos viajan a un punto central | ❌ Contradice "no centralizar los registros crudos" |
| RabbitMQ por sede | Ligero, fácil de operar, buen enrutado | Cola que se vacía al consumir: sin re-lectura ni replay tras un fallo; sin conector oficial para Spark | ⚠️ Cumple C1, pero complica la recuperación exacta (C3) |
| Redpanda por sede | API compatible con Kafka, sin JVM, menor consumo de memoria | Menos documentación y uso en la asignatura; licencia distinta a Apache | ✅ Alternativa real y viable: la migración sería casi transparente |
| MQTT (Mosquitto) | Estándar IoT, muy ligero | Pensado para mensajes efímeros, sin almacenamiento largo ni re-lectura | ⚠️ |
| HTTP directo a la sede (sin bus) | Mínimo número de piezas | Sin buffer: si el procesamiento cae, se pierden eventos; acopla productor y consumidor | ⚠️ |

**Por qué Kafka por sede.** E2 obliga a que el dato crudo nazca y muera en
su sede, así que el bus tiene que ser local. Kafka aporta lo que más nos
importaba para la exactitud (C3): si un job de Spark cae, se reanuda desde
el último offset confirmado y no se pierde ni se duplica ningún evento
dentro del bus. Redpanda habría sido igual de válida y más ligera; se
eligió Kafka por ser la referencia del enunciado y por su ecosistema (C6).

### 3.2 Procesamiento

Limpieza, cuarentena y cálculo de agregados (Bronze → Silver → Gold).

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **Apache Spark 4.2 / PySpark (elegida)** | Misma API para batch y streaming: las reglas de `cleaning.py` se escriben una vez (C4); `foreachBatch` permite dos salidas (Silver y cuarentena) y el upsert a Postgres; ecosistema enorme | Cada job es una JVM de ~0,7 GB (9 en total con 3 sedes); micro-batches de segundos, no milisegundos | ✅ Corre dentro de cada sede |
| Apache Flink (PyFlink) | Streaming nativo con estado y latencias muy bajas; deduplicación con estado más natural | API de Python menos madura; batch y streaming menos unificados en Python; sin experiencia previa del equipo | ✅ Viable; no necesitamos latencia de milisegundos |
| Kafka Streams / ksqlDB | Sin clúster aparte, vive junto al broker | Solo streaming (no carga el histórico CSV); Kafka Streams es Java | ⚠️ Obligaría a reinyectar el histórico en Kafka |
| pandas / Polars en scripts | Mínimo consumo y complejidad; suficiente para la muestra de 999 viajes | Sin streaming, checkpoints ni tolerancia a fallos; no escala al dataset completo de NYC | ⚠️ Válido para la PdC, no para el sistema real |
| Hadoop MapReduce | Probado a gran escala | Solo batch, lento, obsoleto frente a Spark | ❌ No cubre tiempo real |

**Por qué Spark.** El criterio decisivo fue C4: el histórico y el tiempo real
pasan por **el mismo** `silver.py` y las mismas reglas, lo que elimina
toda una clase de errores de divergencia y es la base de la exactitud que
mide M3 (0 diferencias). El precio es la memoria: con tres sedes en un
portátil fue necesario parar Kafka y Spark una vez cargado Gold.

**Lección aprendida.** Integrar batch y streaming sobre la misma ruta de
ficheros no es trivial en Spark 4.2: el *file sink* de streaming oculta los
ficheros que no están en su `_spark_metadata`, unir dos *file streams* falla
si solo uno trae datos, y un stream arrancado sobre un sink aún vacío
desalinea las columnas de partición. Se resolvió separando `bronze/historical`
y `bronze/realtime` y procesándolos con dos queries secuenciales (#94).

### 3.3 Lakehouse (Bronze / Silver)

Dónde se guardan los datos crudos (Bronze), limpios (Silver) y rechazados
(cuarentena) dentro de cada sede.

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **Parquet particionado en volumen local (elegida)** | Columnar y comprimido; esquema embebido; cero servicios extra; partición por `site_id` / `source` | Sin transacciones: la deduplicación entre micro-batches y el reprocesado hay que gestionarlos a mano | ✅ El volumen es de la sede |
| Delta Lake o Apache Iceberg sobre Parquet | Transacciones ACID, `MERGE` (upsert y deduplicación real), *time travel*, evolución de esquema | Una dependencia más en Spark; más conceptos para el equipo | ✅ **Mejora recomendada**: habría evitado los problemas de la lección anterior |
| MinIO (S3) por sede + Parquet | API S3 estándar, separa cómputo y almacenamiento | Un servicio más por sede sin beneficio claro en una sola máquina | ✅ Muy útil si se añade E8 (§5.3) |
| HDFS | Almacenamiento distribuido clásico | Clúster pesado (NameNode, DataNodes) para 60 KB por sede | ✅ Desproporcionado |
| Guardar el crudo directamente en Postgres | Una sola tecnología de almacenamiento | Mezcla crudo y servido en la misma base; peor para análisis masivo | ⚠️ Acerca el crudo a la puerta de salida |

**Por qué Parquet plano.** Es la opción más simple que cumple E2: cada sede
tiene su volumen y nada se comparte. Delta o Iceberg serían el siguiente
paso natural (idempotencia y deduplicación transaccional), y el diseño lo
permite cambiando solo el formato de escritura y lectura de los jobs.

### 3.4 Serving (Gold + API de sede)

Qué se almacena para servir y por dónde sale de la sede.

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **PostgreSQL por sede + `site_api` (FastAPI) (elegida)** | Upsert aditivo (`ON CONFLICT … col = col + EXCLUDED.col`) en la misma transacción que la tabla de control de batches → efectivamente *exactly-once*; esquema fijo con solo `trip_count` y `sum_*`; la API es la única puerta y decide qué sale | Un Postgres por sede; la API hay que mantenerla a mano | ✅ Solo salen agregados (M2: 0 bytes crudos) |
| Exponer Postgres directamente (SQL remoto) | Consultas arbitrarias, sin código de API | Cualquiera con credenciales puede leer cualquier tabla, incluida la cuarentena con viajes completos | ❌ Es justo el riesgo que M2 marca como `xfail` (puerto 5432–5434 publicado) |
| MongoDB | Esquema flexible; `$inc` permite upserts aditivos | La flexibilidad de esquema juega en contra del contrato "solo agregados combinables" | ✅ Viable |
| ClickHouse / DuckDB | Muy rápidos en consultas analíticas | Sobredimensionado para decenas de filas agregadas por sede | ✅ Interesante a gran escala |
| GraphQL en lugar de REST | El cliente pide exactamente los campos que quiere | Más superficie para pedir combinaciones finas de filtros | ⚠️ Complica garantizar qué sale |

**Por qué Postgres + API REST.** E2.4 exige no transferir crudos
innecesariamente: la forma más robusta de garantizarlo es que la sede solo
tenga **una** salida y que esa salida, por contrato, solo sepa devolver
conteos y sumas. El esquema de Gold (`sum_*`, nunca medias) hace además
que las respuestas se puedan sumar entre sedes sin error (C3).

### 3.5 Consulta unificada

Cómo se responde una pregunta que necesita datos de las tres sedes.

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **Coordinador sin estado replicado en las 3 sedes (elegida)** | Consulta las 3 `site_api` en paralelo y suma; calcula las medias una sola vez (Σ sumas / Σ conteos); sin estado que sincronizar; si una sede cae responde con las otras dos (`partial`); si cae una réplica, el cliente usa la siguiente | Cada pregunta depende de que las sedes respondan en ese momento (latencia de la más lenta, acotada por timeout) | ✅ |
| Centralizar el crudo en un almacén central | Consultas SQL arbitrarias y rápidas | Es exactamente lo que E2 prohíbe | ❌ |
| Replicar Gold a una base central (replicación lógica de Postgres o CDC con Debezium) | Consultas rápidas aunque una sede esté caída; solo viajan agregados | Datos potencialmente desfasados; un punto central nuevo (y único punto de fallo si no se replica); más piezas | ✅ Alternativa válida, más compleja |
| Motor federado (Trino/Presto) o `postgres_fdw` | SQL estándar sobre las tres bases a la vez | Necesita acceso SQL directo a cada Postgres (todas sus tablas, incluida la cuarentena); el coordinador de Trino es único; pesado | ⚠️ Abre la puerta a leer crudos |
| Media de medias (cada sede devuelve su media) | Respuestas más pequeñas | Resultado incorrecto cuando los volúmenes difieren | ❌ M3 mide hasta un 48 % de error |

**Respuesta a E2.1 (qué se replica, qué se agrega, qué se consulta):**

| Dato | Dónde vive | ¿Sale de la sede? |
|---|---|---|
| Viajes crudos (CSV, Kafka, Bronze) | Solo en su sede | Nunca |
| Viajes limpios y cuarentena (Silver) | Solo en su sede | Nunca |
| Agregados combinables (Gold: conteos y sumas por hora, día, zona, pago) | Postgres de la sede | Sí, bajo demanda, por la `site_api` |
| Medias globales | No se almacenan | Las calcula el coordinador en cada consulta |
| Coordinador (código, sin datos) | Replicado en las 3 sedes | — |
| **Replicación de datos** | **Ninguna** | — |

**Respuesta a E2.2 (qué pasa si una sede no está disponible)**, medida en M1:

- Si cae la API de una sede, cualquier coordinador responde con las otras
  dos y lo indica (`partial: true`, `sites_failed`): 100 % de disponibilidad.
- Si una sede se queda colgada, el coordinador la da por perdida a los 5 s
  y responde igual; el cliente espera más (10 s) para no descartar esa
  respuesta parcial (#90).
- Si cae el coordinador de una sede, el cliente usa el siguiente en orden
  Central → Chamartín → Atocha: 100 % de disponibilidad.
- Solo sin ninguna sede disponible no hay respuesta.

### 3.6 Despliegue

| Alternativa | Ventajas | Inconvenientes | Encaje con E2 |
|---|---|---|---|
| **Docker Compose: una plantilla + `.env` por sede (elegida)** | Cada sede es un proyecto aislado con su red interna; solo `site_api` y coordinador comparten la red `pids-interconnect`; un único fichero que mantener; Makefile para operar | Una sola máquina; sin autoescalado ni reprogramación automática de contenedores | ✅ El aislamiento de red entre sedes está verificado por M2 |
| Kubernetes (k3s, minikube) | *Namespace* por sede, `NetworkPolicy` para garantizar que solo las APIs se ven entre sedes, autorreparación, escalado | Curva de aprendizaje y recursos altos para la PdC | ✅ Sería el paso a producción |
| Docker Swarm | Multi-máquina con poca configuración, redes *overlay* | Menos usado hoy; menos herramientas | ✅ Buena opción para tres máquinas físicas reales |
| Tres ficheros compose distintos | Máxima libertad por sede | Tres ficheros casi iguales que divergen con el tiempo | ✅ Peor mantenibilidad |

**Por qué Compose.** Permite simular tres sedes independientes en un portátil
con el mismo aislamiento que exige E2 (Kafka, Spark y Postgres no son
alcanzables desde otra sede). Si las sedes estuvieran en máquinas
distintas, el diseño ya lo contempla: basta con cambiar las URLs
`SITE_API_URL_*` del `.env`.

---

## 4. Qué validaron las métricas

Las tres métricas propias (issues #66–#68) comprueban que las decisiones
anteriores cumplen E2 en el despliegue real, no solo en el papel:

| Métrica | Pregunta de E2 | Resultado | Decisión que valida |
|---|---|---|---|
| **M1 · Disponibilidad** | ¿Qué pasa si cae una sede? | 100 % de consultas respondidas en los 8 escenarios con al menos una sede viva; 100 % de sedes caídas bien señaladas | Coordinador replicado + failover (§3.5) |
| **M2 · Transferencia de crudos** | ¿Salen datos crudos de la sede? | 0 bytes crudos y 0 `trip_id` en todas las respuestas; lo que sale es un 6 % del tamaño del crudo de la sede | API como única puerta + agregados (§3.4) |
| **M3 · Exactitud** | ¿La respuesta unificada es correcta? | 0 diferencias frente a un cálculo centralizado (994 viajes); la media de medias habría errado hasta un 48 % | Agregados combinables + medias en el coordinador (§3.5) |

Además, las métricas detectaron y permitieron corregir tres fallos antes
de la entrega: el timeout del cliente de failover (#90), la imagen de
Spark rota por un cambio de Debian (#92) y que el histórico nunca llegaba
a Gold (#94).

---

## 5. Adaptación a otras restricciones

La arquitectura por capas permite cambiar de restricción tocando piezas
concretas. Para cada una: qué ya tenemos, qué cambiaría y cómo lo mediríamos.

### 5.1 E3 · Privacidad total

> Ningún dato individual puede ser expuesto. Agregar o anonimizar antes de
> hacer consultable, enmascarar resultados con pocos registros, rechazar
> consultas de viajes individuales y registrar las decisiones de privacidad.

**Lo que ya cumple el diseño actual.** Solo se exponen agregados y ningún
endpoint devuelve viajes (M2: 0 bytes crudos). La protección se aplica igual
al histórico y al tiempo real, porque ambos acaban en las mismas tablas Gold.

**Lo que falta.** Un agregado de un solo viaje *es* un viaje. M2 contó
**23 grupos con `trip_count = 1`** (sobre todo en `/metrics/zone`): con E3
serían una fuga.

| Cambio | Dónde | Detalle |
|---|---|---|
| Umbral de k-anonimato | `site_api` y coordinador | Suprimir o agrupar en "otros" los grupos con `trip_count < k` (p. ej. k = 5). El coordinador lo aplica **después** de combinar, porque un grupo pequeño en una sede puede ser grande en total |
| Generalizar claves finas | Gold | Zona de recogida → distrito (*borough*) con la tabla de zonas de NYC; hora → franja |
| Evitar ataques por diferencia | `site_api` | Limitar la granularidad de `date_from` / `date_to` y rechazar combinaciones de filtros que aíslen pocos viajes (restar dos consultas casi iguales revela un viaje) |
| Cerrar el acceso directo | Compose | Quitar el puerto publicado de Postgres (hoy `xfail` en M2) y limitar la retención de `silver_rejected`, que guarda viajes completos |
| Registro de decisiones | `site_api` | Tabla de auditoría con cada consulta rechazada o enmascarada y el motivo; el chatbot ofrece la alternativa agregada |

**Métricas propuestas:** grupos publicados con menos de k viajes (objetivo 0);
porcentaje de consultas de viaje individual rechazadas (objetivo 100 %);
utilidad retenida (porcentaje de viajes cubiertos por grupos publicados).

### 5.2 E4 · Varios consumidores

> Métricas, detección de anomalías y auditoría consumen los mismos eventos
> de forma independiente; cada proceso puede detenerse o escalarse sin
> bloquear a los demás.

**Lo que ya cumple el diseño actual.** Kafka está pensado para esto: cada
consumidor usa su propio *consumer group* con sus propios offsets, y los
eventos se retienen aunque otro consumidor ya los haya leído.

**Lo que falta.** Hoy hay un único consumidor (`stream_bronze`); el resto
del pipeline lee ficheros de Bronze.

| Cambio | Dónde | Detalle |
|---|---|---|
| Consumidores independientes | Compose | Servicios `anomalies` y `audit` con su propio contenedor, *consumer group* y checkpoint; `restart` independiente |
| Escalar un consumidor | Kafka | Topic con varias particiones (hoy 1) para repartir la carga entre instancias del mismo grupo |
| Contrato común | `src/common/schema.py` | Todos validan contra el mismo esquema canónico; un evento inválido va a su cuarentena sin bloquear a los demás |
| Coherencia entre procesos | APIs | Cada consumidor publica hasta qué offset o marca temporal ha procesado; el chatbot puede decir "anomalías calculadas hasta las 10:42" |
| Auditoría completa | Kafka | Retención del topic igual o mayor que la ventana de auditoría, o archivado del topic a Bronze |

**Métricas propuestas:** *lag* por consumidor; independencia (parar
`anomalies` y medir que métricas y auditoría siguen procesando, al estilo
de M1); eventos perdidos por consumidor (objetivo 0).

### 5.3 E8 · Retención y ciclo de vida de los datos

> Los datos recientes deben consultarse rápido y los antiguos conservarse
> años con coste reducido; ruta de archivado y recuperación; informar si una
> respuesta viene de datos recientes o archivados.

**Lo que ya cumple el diseño actual.** Separación en capas (Bronze, Silver,
Gold) y Gold pequeño y agregado, ideal como "capa caliente".

**Lo que falta.** No hay ninguna política: todo vive para siempre en el
volumen de la sede.

| Cambio | Dónde | Detalle |
|---|---|---|
| Partición por fecha | Bronze y Silver | Añadir `pickup_date` a la partición (hoy `site_id` / `source`) para poder mover días enteros |
| Tres niveles de almacenamiento | Cada sede | **Caliente**: Gold reciente en Postgres. **Templado**: Parquet local. **Frío**: Parquet comprimido en almacenamiento de objetos (MinIO/S3) **de la propia sede**: E2 sigue aplicando al archivo |
| Job de archivado periódico | Spark batch + planificador | Mueve particiones antiguas al nivel frío y reduce la granularidad de Gold antiguo (hora → día → mes) |
| Ruta de recuperación | Spark batch | "Rehidrata" un rango de fechas desde el nivel frío a una tabla temporal consultable |
| Informar del origen | `site_api` y coordinador | Campo `data_tier` (`reciente` / `archivado`) en cada respuesta; el chatbot avisa de que la consulta puede tardar más |

**Métricas propuestas:** latencia p95 de consultas recientes frente a
archivadas; coste de almacenamiento por GB y mes; tiempo de recuperación de
un mes archivado.

### 5.4 Resumen del esfuerzo de adaptación

| Restricción | Capas afectadas | Esfuerzo estimado | Por qué |
|---|---|---|---|
| **E3** · Privacidad | Serving, consulta unificada, despliegue | Bajo–medio | La base ya es "solo agregados"; faltan umbrales, generalización y auditoría |
| **E4** · Varios consumidores | Ingesta, procesamiento, despliegue | Medio | Kafka ya lo soporta; hay que escribir y desplegar los nuevos consumidores |
| **E8** · Retención | Lakehouse, procesamiento, serving | Medio–alto | Requiere particionado por fecha, un nivel de almacenamiento nuevo y jobs de archivado y recuperación |

En los tres casos se mantiene la decisión central de E2: **ningún dato
crudo sale de su sede**. La adaptación se hace dentro de cada sede y en el
contrato de su API, no centralizando datos.
