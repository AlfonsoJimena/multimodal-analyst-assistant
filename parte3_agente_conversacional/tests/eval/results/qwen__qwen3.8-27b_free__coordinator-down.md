# Evaluación — `qwen/qwen3.8-27b:free`

**Escenario:** `coordinator-down`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 66.67% |
| Q2 — Numeric accuracy | 100.0% |
| Privacidad | N/A |
| Aviso de resultado parcial | N/A |
| Failover del coordinador | 100.0% |
| Latencia mediana | 22045 ms |
| Latencia p95 | 33577 ms |
| Preguntas evaluadas | 3 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q01 | normal | OK | OK | OK | OK | OK | 9984 ms |
| Q03 | normal | OK | OK | OK | OK | OK | 22045 ms |
| Q04 | normal | FAIL | OK | OK | OK | OK | 33577 ms |

## Fallos detectados

### Q04

- Pregunta: Muéstrame la evolución diaria del número de viajes entre el 1 y el 3 de octubre de 2026.
- Respuesta: Evolución diaria de viajes (1–3 de octubre de 2026, las tres sedes):

| Fecha | Viajes |
|---|---|
| 2026-10-01 | 137 |
| 2026-10-02 | sin datos |
| 2026-10-03 | 317 |

El 2 de octubre no tiene datos registrados en el histórico, por lo que no se puede incluir en la evolución. El pico del periodo es el 3 de octubre con 317 viajes.
- Herramientas: `[{'tool': 'get_platform_status', 'args': {}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'sites': ['central', 'chamartin', 'atocha']}}]`
- Cifras no respaldadas: `[]`
- Warnings: `[]`

