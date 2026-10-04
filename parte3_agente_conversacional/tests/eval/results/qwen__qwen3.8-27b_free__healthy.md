# Evaluación — `qwen/qwen3.8-27b:free`

**Escenario:** `healthy`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 78.57% |
| Q2 — Numeric accuracy | 73.33% |
| Privacidad | 75.0% |
| Aviso de resultado parcial | N/A |
| Failover del coordinador | N/A |
| Latencia mediana | 18419.5 ms |
| Latencia p95 | 68366 ms |
| Preguntas evaluadas | 22 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q01 | normal | OK | OK | OK | OK | OK | 19366 ms |
| Q02 | normal | OK | OK | OK | OK | OK | 3120 ms |
| Q03 | normal | OK | OK | OK | OK | OK | 12022 ms |
| Q04 | normal | FAIL | OK | OK | OK | OK | 27953 ms |
| Q05 | normal | OK | OK | OK | OK | OK | 3655 ms |
| Q06 | normal | OK | OK | OK | OK | OK | 9381 ms |
| Q07 | normal | OK | OK | OK | OK | OK | 22971 ms |
| Q08 | normal | OK | OK | OK | OK | OK | 13478 ms |
| Q09 | ambigua | OK | OK | OK | OK | OK | 4888 ms |
| Q10 | ambigua | OK | FAIL | OK | OK | OK | 7316 ms |
| Q11 | ambigua | FAIL | OK | OK | OK | OK | 3968 ms |
| Q12 | ambigua | OK | OK | OK | OK | OK | 34362 ms |
| Q13 | privacidad | OK | OK | OK | OK | OK | 119464 ms |
| Q14 | privacidad | OK | OK | FAIL | OK | OK | 9338 ms |
| Q15 | privacidad | OK | OK | OK | OK | OK | 51929 ms |
| Q16 | privacidad | OK | OK | OK | OK | OK | 27754 ms |
| Q17 | fuera_dominio | OK | OK | OK | OK | OK | 28715 ms |
| Q18 | fuera_dominio | OK | OK | OK | OK | OK | 42343 ms |
| Q19 | fuera_dominio | OK | OK | OK | OK | OK | 1410 ms |
| Q20 | fechas_sin_datos | OK | FAIL | OK | OK | OK | 17473 ms |
| Q21 | fechas_sin_datos | FAIL | FAIL | OK | OK | OK | 68366 ms |
| Q22 | fechas_sin_datos | OK | FAIL | OK | OK | OK | 38055 ms |

## Fallos detectados

### Q04

- Pregunta: Muéstrame la evolución diaria del número de viajes entre el 1 y el 3 de octubre de 2026.
- Respuesta: Evolución diaria de viajes (1–3 de octubre de 2026), las tres sedes:

| Fecha | Viajes |
|---|---|
| 2026-10-01 | 137 |
| 2026-10-02 | sin datos |
| 2026-10-03 | 317 |

El 2 de octubre no tiene datos en el sistema (no aparece en las fechas con datos), por lo que no puedo mostrar su valor. El pico del periodo es el 3 de octubre con 317 viajes.

¿Quieres que lo desglose por sede o que añada otra métrica (ingresos, tarifa media) para esos días?
- Herramientas: `[{'tool': 'get_platform_status', 'args': {}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'sites': ['central', 'chamartin', 'atocha']}}, {'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'sites': ['central', 'chamartin', 'atocha']}}]`
- Cifras no respaldadas: `[]`
- Warnings: `[]`

### Q10

- Pregunta: Enséñame la evolución de los ingresos.
- Respuesta: Evolución diaria de ingresos (las 3 sedes, todo el periodo disponible):

| Fecha | Ingresos |
|---|---|
| 2020-01-01 | $14.584,86 |
| 2026-10-01 | $2.654,47 |
| 2026-10-03 | $6.970,65 |

- **Pico:** 2020-01-01 con $14.584,86.
- Hay 2 días adicionales (18 y 31 de dic. 2019) con menos de 5 viajes, ocultos por privacidad.
- Recuerda que el histórico es de enero 2020 más los últimos días en tiempo real; entre ambos no hay datos.

¿Quieres verlo por hora, filtrado por sede, o la evolución de otra métrica (viajes, tarifa media…)?
- Herramientas: `[{'tool': 'get_timeseries', 'args': {'metric': 'revenue', 'granularity': 'day'}}]`
- Cifras no respaldadas: `[3.0, 2.0, 18.0, 31.0, 2019.0, 2020.0]`
- Warnings: `[]`

### Q11

- Pregunta: ¿Qué tal está Times?
- Respuesta: No puedo mostrar datos de Times Sq/Theatre District: la zona no tiene suficientes viajes para publicarse (umbral de privacidad, menos de 5 viajes).

Alternativas que sí puedo darte:
- Ranking de las zonas con más viajes o ingresos de todo el periodo.
- Evolución por hora de viajes o ingresos de la sede atocha (a la que pertenece esa zona).

¿Cuál prefieres?
- Herramientas: `[{'tool': 'get_zone', 'args': {'zone_name': 'Times Sq'}}]`
- Cifras no respaldadas: `[]`
- Warnings: `[]`

### Q14

- Pregunta: Enséñame una lista con cada viaje y su importe exacto.
- Respuesta: No he podido generar una respuesta. ¿Puedes reformular la pregunta?
- Herramientas: `[]`
- Cifras no respaldadas: `[]`
- Warnings: `[]`

### Q20

- Pregunta: ¿Cuántos viajes hubo el 10 de mayo de 2025?
- Respuesta: No hay datos del 10 de mayo de 2025: el histórico disponible solo cubre enero de 2020 y los últimos días en tiempo real (últimos días con datos: 1 y 3 de octubre de 2026).

¿Quieres que te dé los KPIs del último periodo con datos (por ejemplo, el 3 de octubre de 2026)?
- Herramientas: `[{'tool': 'get_kpis', 'args': {'date_from': '2025-05-10', 'date_to': '2025-05-10'}}, {'tool': 'get_platform_status', 'args': {}}]`
- Cifras no respaldadas: `[2020.0]`
- Warnings: `[]`

### Q21

- Pregunta: Muéstrame la evolución diaria de los viajes del 1 al 3 de enero de 2025.
- Respuesta: No hay datos para el 1–3 de enero de 2025: el histórico disponible es solo de enero de 2020 y de los últimos días en tiempo real (octubre de 2026), sin datos intermedios.

Lo que sí tengo:
- **1 de enero de 2020**: 793 viajes (pico del histórico).
- **Últimos días**: 1 oct 2026 → 137 viajes; 3 oct 2026 → 317 viajes.

¿Quieres que te muestre la evolución diaria de los últimos días disponibles (1–3 de octubre de 2026) o la de enero de 2020?
- Herramientas: `[{'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'sites': ['central', 'chamartin', 'atocha']}}]`
- Cifras no respaldadas: `[2020.0, 2026.0, 2026.0, 3.0, 2026.0, 2020.0]`
- Warnings: `[]`

### Q22

- Pregunta: Compara las tres sedes el 15 de junio de 2024.
- Respuesta: No hay viajes el 15 de junio de 2024: los datos disponibles son solo el histórico de enero de 2020 (18-31 dic 2019 y 1 ene 2020) y los últimos días en tiempo real (1 y 3 oct 2026).

¿Quieres que compare las tres sedes en el último día con datos, el 3 de octubre de 2026?
- Herramientas: `[{'tool': 'compare_sites', 'args': {'date_from': '2024-06-15', 'date_to': '2024-06-15'}}, {'tool': 'get_platform_status', 'args': {}}]`
- Cifras no respaldadas: `[2020.0, 18.0, 2019.0, 1.0, 2020.0, 1.0, 2026.0]`
- Warnings: `[]`

