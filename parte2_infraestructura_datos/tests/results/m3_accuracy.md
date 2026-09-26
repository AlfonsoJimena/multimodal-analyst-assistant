# M3 · Exactitud federada frente a cálculo centralizado

Referencia: cálculo centralizado en Python (sin Spark) sobre `data/prepared/`, con las reglas de `cleaning.py`. Conteos y sumas de dinero en `Decimal`: la diferencia admitida es 0.

| Origen | Endpoint | Claves comparadas | Viajes esperados | Viajes obtenidos | Claves con diferencias |
|---|---|---|---|---|---|
| central | `/metrics/hourly` | 1 | 316 | 316 | **0** |
| central | `/metrics/daily` | 1 | 316 | 316 | **0** |
| central | `/metrics/zone` | 27 | 316 | 316 | **0** |
| central | `/metrics/payment` | 3 | 316 | 316 | **0** |
| chamartin | `/metrics/hourly` | 2 | 307 | 307 | **0** |
| chamartin | `/metrics/daily` | 2 | 307 | 307 | **0** |
| chamartin | `/metrics/zone` | 26 | 307 | 307 | **0** |
| chamartin | `/metrics/payment` | 3 | 307 | 307 | **0** |
| atocha | `/metrics/hourly` | 2 | 371 | 371 | **0** |
| atocha | `/metrics/daily` | 2 | 371 | 371 | **0** |
| atocha | `/metrics/zone` | 29 | 371 | 371 | **0** |
| atocha | `/metrics/payment` | 4 | 371 | 371 | **0** |
| coordinador | `/metrics/hourly` | 3 | 994 | 994 | **0** |
| coordinador | `/metrics/daily` | 3 | 994 | 994 | **0** |
| coordinador | `/metrics/zone` | 82 | 994 | 994 | **0** |
| coordinador | `/metrics/payment` | 4 | 994 | 994 | **0** |

## Error que evita el diseño: «media de medias»

Tarifa media calculada como media de las medias de cada sede, frente a Σ sumas / Σ conteos (lo que hace el coordinador).

| Grupo | Viajes por sede | Media correcta | Media de medias | Error relativo |
|---|---|---|---|---|
| global: todas | 316, 307, 371 | 12.7952 | 12.8454 | 0.39% |
| por método de pago: 1 | 213, 212, 260 | 12.6218 | 12.7122 | 0.72% |
| por método de pago: 2 | 101, 94, 103 | 12.8960 | 12.8857 | 0.08% |
| por método de pago: 3 | 2, 7 | 23.3333 | 34.6429 | 48.47% |
| por método de pago: 4 | 1, 1 | 9.7500 | 9.7500 | 0.00% |
