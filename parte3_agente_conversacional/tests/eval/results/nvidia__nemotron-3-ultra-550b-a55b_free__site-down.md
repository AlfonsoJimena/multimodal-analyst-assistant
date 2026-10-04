# Evaluación — `nvidia/nemotron-3-ultra-550b-a55b:free`

**Escenario:** `site-down`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 66.67% |
| Q2 — Numeric accuracy | 100.0% |
| Privacidad | N/A |
| Aviso de resultado parcial | 100.0% |
| Failover del coordinador | N/A |
| Latencia mediana | 23641 ms |
| Latencia p95 | 29507 ms |
| Preguntas evaluadas | 3 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q23 | sede_caida | OK | OK | OK | OK | OK | 23641 ms |
| Q24 | sede_caida | OK | OK | OK | OK | OK | 8401 ms |
| Q25 | sede_caida | FAIL | OK | OK | OK | OK | 29507 ms |

## Fallos detectados

### Q25

- Pregunta: Muéstrame la evolución diaria de los viajes el 1 de octubre de 2026.
- Respuesta: Evolución horaria de viajes el **1 de octubre de 2026** (granularidad = hora, único día disponible):

| Hora (UTC) | Viajes |
|------------|--------|
| 16:00      | 64     |

**Pico:** 16:00 con 64 viajes.

⚠️ **Resultado parcial**: solo respondieron las sedes **central** y **chamartin**; **atocha** no devolvió datos, por lo que las cifras no incluyen esa sede.
- Herramientas: `[{'tool': 'get_timeseries', 'args': {'date_to': '2026-10-01', 'date_from': '2026-10-01', 'metric': 'trips', 'granularity': 'hour'}}]`
- Cifras no respaldadas: `[]`
- Warnings: `['Resultado parcial de get_timeseries: no han respondido atocha; las cifras no incluyen esas sedes.']`

