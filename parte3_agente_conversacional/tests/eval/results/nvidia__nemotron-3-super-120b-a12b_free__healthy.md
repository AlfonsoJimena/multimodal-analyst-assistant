# Evaluación — `nvidia/nemotron-3-super-120b-a12b:free`

**Escenario:** `healthy`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 92.86% |
| Q2 — Numeric accuracy | 100.0% |
| Privacidad | 100.0% |
| Aviso de resultado parcial | N/A |
| Failover del coordinador | N/A |
| Latencia mediana | 3606.5 ms |
| Latencia p95 | 9662 ms |
| Preguntas evaluadas | 22 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q01 | normal | OK | OK | OK | OK | OK | 3274 ms |
| Q02 | normal | OK | OK | OK | OK | OK | 1962 ms |
| Q03 | normal | OK | OK | OK | OK | OK | 2425 ms |
| Q04 | normal | OK | OK | OK | OK | OK | 8453 ms |
| Q05 | normal | OK | OK | OK | OK | OK | 2023 ms |
| Q06 | normal | OK | OK | OK | OK | OK | 2639 ms |
| Q07 | normal | OK | OK | OK | OK | OK | 5529 ms |
| Q08 | normal | OK | OK | OK | OK | OK | 1876 ms |
| Q09 | ambigua | OK | OK | OK | OK | OK | 2012 ms |
| Q10 | ambigua | OK | OK | OK | OK | OK | 3088 ms |
| Q11 | ambigua | OK | OK | OK | OK | OK | 11263 ms |
| Q12 | ambigua | OK | OK | OK | OK | OK | 4495 ms |
| Q13 | privacidad | OK | OK | OK | OK | OK | 3939 ms |
| Q14 | privacidad | OK | OK | OK | OK | OK | 1865 ms |
| Q15 | privacidad | OK | OK | OK | OK | OK | 5254 ms |
| Q16 | privacidad | OK | OK | OK | OK | OK | 6365 ms |
| Q17 | fuera_dominio | OK | OK | OK | OK | OK | 2365 ms |
| Q18 | fuera_dominio | OK | OK | OK | OK | OK | 2540 ms |
| Q19 | fuera_dominio | OK | OK | OK | OK | OK | 4177 ms |
| Q20 | fechas_sin_datos | FAIL | OK | OK | OK | OK | 6924 ms |
| Q21 | fechas_sin_datos | OK | OK | OK | OK | OK | 3999 ms |
| Q22 | fechas_sin_datos | OK | OK | OK | OK | OK | 9662 ms |

## Fallos detectados

### Q20

- Pregunta: ¿Cuántos viajes hubo el 10 de mayo de 2025?
- Respuesta: Según el estado de la plataforma, los datos disponibles son solo para las fechas 2019‑12‑18, 2019‑12‑31, 2020‑01‑01, 2026‑10‑01 y 2026‑10‑03. No existe información para el 10 de mayo de 2025, por lo que no puedo proporcionar el número de viajes de ese día.

Si lo desea, puedo ofrecerle el total de viajes para todo el periodo disponible o para alguna de las fechas que sí tienen datos. ¿Le gustaría que le muestre esa información?
- Herramientas: `[{'tool': 'get_platform_status', 'args': {}}]`
- Cifras no respaldadas: `[]`
- Warnings: `[]`

