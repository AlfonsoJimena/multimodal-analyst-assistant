# M2 · Transferencia de datos crudos fuera de cada sede

## Tráfico por sede

Barrido completo = una llamada a cada `/metrics/*` de la `site_api`. Bytes crudos de la sede = sus CSV preparados (histórico + realtime).

| Sede | Bytes crudos en la sede | Bytes que salen (barrido) | Ratio | Bytes crudos que salen | trip_id filtrados | Viajes en Gold | Grupos con 1 viaje |
|---|---|---|---|---|---|---|---|
| central | 58,544 | 3,538 | 0.06 | **0** | 0 | 64 | 9 |
| chamartin | 57,244 | 3,528 | 0.06 | **0** | 0 | 61 | 10 |
| atocha | 68,153 | 3,761 | 0.06 | **0** | 0 | 73 | 4 |

## Respuestas por endpoint

| Sede | Endpoint | HTTP | Bytes | Filas | Campos no agregados |
|---|---|---|---|---|---|
| central | `/metrics/hourly` | 200 | 175 | 1 | — |
| central | `/metrics/daily` | 200 | 166 | 1 | — |
| central | `/metrics/zone` | 200 | 2,765 | 19 | — |
| central | `/metrics/payment` | 200 | 432 | 3 | — |
| central | `/quarantine/summary` | 200 | 2 | — | — |
| central | `/health` | 200 | 35 | — | — |
| central | `/prometheus` | 200 | 14,452 | — | — |
| chamartin | `/metrics/hourly` | 200 | 619 | 4 | — |
| chamartin | `/metrics/daily` | 200 | 165 | 1 | — |
| chamartin | `/metrics/zone` | 200 | 2,301 | 16 | — |
| chamartin | `/metrics/payment` | 200 | 443 | 3 | — |
| chamartin | `/quarantine/summary` | 200 | 2 | — | — |
| chamartin | `/health` | 200 | 37 | — | — |
| chamartin | `/prometheus` | 200 | 14,440 | — | — |
| atocha | `/metrics/hourly` | 200 | 174 | 1 | — |
| atocha | `/metrics/daily` | 200 | 165 | 1 | — |
| atocha | `/metrics/zone` | 200 | 2,992 | 21 | — |
| atocha | `/metrics/payment` | 200 | 430 | 3 | — |
| atocha | `/quarantine/summary` | 200 | 2 | — | — |
| atocha | `/health` | 200 | 34 | — | — |
| atocha | `/prometheus` | 200 | 14,437 | — | — |
| coordinador | `/metrics/hourly` | 200 | 1,210 | 4 | — |
| coordinador | `/metrics/daily` | 200 | 431 | 1 | — |
| coordinador | `/metrics/zone` | 200 | 15,229 | 56 | — |
| coordinador | `/metrics/payment` | 200 | 1,228 | 4 | — |

## Superficie de exposición

| Sede | Servicio | Puertos publicados | En pids-interconnect | Acceso a datos crudos | Valoración |
|---|---|---|---|---|---|
| central | coordinator | 0.0.0.0:8100->8000/tcp | sí | no | OK: solo agregados |
| central | kafka | — | no | sí | interno |
| central | postgres | 0.0.0.0:5432->5432/tcp | no | sí | ⚠ expone datos no agregados |
| central | producer | 0.0.0.0:9000->9000/tcp | no | sí | OK: solo métricas técnicas |
| central | site_api | 0.0.0.0:8000->8000/tcp | sí | no | OK: solo agregados |
| central | spark_silver | — | no | sí | interno |
| central | spark_sink_postgres | — | no | sí | interno |
| central | spark_stream_bronze | — | no | sí | interno |
| chamartin | coordinator | 0.0.0.0:8101->8000/tcp | sí | no | OK: solo agregados |
| chamartin | kafka | — | no | sí | interno |
| chamartin | postgres | 0.0.0.0:5433->5432/tcp | no | sí | ⚠ expone datos no agregados |
| chamartin | producer | 0.0.0.0:9001->9000/tcp | no | sí | OK: solo métricas técnicas |
| chamartin | site_api | 0.0.0.0:8001->8000/tcp | sí | no | OK: solo agregados |
| chamartin | spark_silver | — | no | sí | interno |
| chamartin | spark_sink_postgres | — | no | sí | interno |
| chamartin | spark_stream_bronze | — | no | sí | interno |
| atocha | coordinator | 0.0.0.0:8102->8000/tcp | sí | no | OK: solo agregados |
| atocha | kafka | — | no | sí | interno |
| atocha | postgres | 0.0.0.0:5434->5432/tcp | no | sí | ⚠ expone datos no agregados |
| atocha | producer | 0.0.0.0:9002->9000/tcp | no | sí | OK: solo métricas técnicas |
| atocha | site_api | 0.0.0.0:8002->8000/tcp | sí | no | OK: solo agregados |
| atocha | spark_silver | — | no | sí | interno |
| atocha | spark_sink_postgres | — | no | sí | interno |
| atocha | spark_stream_bronze | — | no | sí | interno |

`producer` tiene acceso a los viajes, pero el puerto que publica solo sirve contadores de Prometheus. La única salida con datos no agregados es el puerto de Postgres (pendiente de decisión, #61).
