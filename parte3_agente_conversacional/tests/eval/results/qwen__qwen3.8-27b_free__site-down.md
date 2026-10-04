# Evaluación — `qwen/qwen3.8-27b:free`

**Escenario:** `site-down`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 66.67% |
| Q2 — Numeric accuracy | 100.0% |
| Privacidad | N/A |
| Aviso de resultado parcial | 66.67% |
| Failover del coordinador | N/A |
| Latencia mediana | 31357 ms |
| Latencia p95 | 41728 ms |
| Preguntas evaluadas | 3 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q23 | sede_caida | OK | OK | OK | OK | OK | 25868 ms |
| Q24 | sede_caida | OK | OK | OK | OK | OK | 31357 ms |
| Q25 | sede_caida | FAIL | OK | OK | FAIL | OK | 41728 ms |

## Fallos detectados

### Q25

- Pregunta: Muéstrame la evolución diaria de los viajes el 1 de octubre de 2026.
- Respuesta: No he conseguido completar la consulta en el número de pasos permitido. ¿Puedes concretar más la pregunta (sede, periodo o métrica)?
- Herramientas: `[{'tool': 'get_platform_status', 'args': {}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'hour', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'hour', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'hour', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'hour', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'hour', 'sites': ['central', 'chamartin', 'atocha']}}]`
- Cifras no respaldadas: `[]`
- Warnings: `['Resultado parcial de get_platform_status: no han respondido atocha; las cifras no incluyen esas sedes.', 'Resultado parcial de get_timeseries: no han respondido atocha; las cifras no incluyen esas sedes.', 'Se alcanzó el límite de 5 rondas de herramientas sin llegar a una respuesta final.']`

