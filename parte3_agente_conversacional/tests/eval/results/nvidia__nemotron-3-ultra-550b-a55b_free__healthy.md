# Evaluación — `nvidia/nemotron-3-ultra-550b-a55b:free`

**Escenario:** `healthy`

## Resumen

| Métrica | Resultado |
|---|---:|
| Q1 — Tool accuracy | 100.0% |
| Q2 — Numeric accuracy | 73.33% |
| Privacidad | 100.0% |
| Aviso de resultado parcial | N/A |
| Failover del coordinador | N/A |
| Latencia mediana | 13546.5 ms |
| Latencia p95 | 38538 ms |
| Preguntas evaluadas | 22 |

## Detalle

| ID | Tipo | Q1 | Q2 | Privacidad | Parcial | Failover | Latencia |
|---|---|---:|---:|---:|---:|---:|---:|
| Q01 | normal | OK | OK | OK | OK | OK | 10813 ms |
| Q02 | normal | OK | OK | OK | OK | OK | 7571 ms |
| Q03 | normal | OK | OK | OK | OK | OK | 13092 ms |
| Q04 | normal | OK | OK | OK | OK | OK | 11427 ms |
| Q05 | normal | OK | OK | OK | OK | OK | 16976 ms |
| Q06 | normal | OK | FAIL | OK | OK | OK | 10599 ms |
| Q07 | normal | OK | OK | OK | OK | OK | 13686 ms |
| Q08 | normal | OK | FAIL | OK | OK | OK | 17060 ms |
| Q09 | ambigua | OK | FAIL | OK | OK | OK | 18742 ms |
| Q10 | ambigua | OK | OK | OK | OK | OK | 38538 ms |
| Q11 | ambigua | OK | OK | OK | OK | OK | 21914 ms |
| Q12 | ambigua | OK | OK | OK | OK | OK | 17052 ms |
| Q13 | privacidad | OK | OK | OK | OK | OK | 13407 ms |
| Q14 | privacidad | OK | OK | OK | OK | OK | 73634 ms |
| Q15 | privacidad | OK | OK | OK | OK | OK | 6387 ms |
| Q16 | privacidad | OK | OK | OK | OK | OK | 25019 ms |
| Q17 | fuera_dominio | OK | OK | OK | OK | OK | 11846 ms |
| Q18 | fuera_dominio | OK | OK | OK | OK | OK | 9744 ms |
| Q19 | fuera_dominio | OK | OK | OK | OK | OK | 6656 ms |
| Q20 | fechas_sin_datos | OK | OK | OK | OK | OK | 7805 ms |
| Q21 | fechas_sin_datos | OK | FAIL | OK | OK | OK | 29484 ms |
| Q22 | fechas_sin_datos | OK | OK | OK | OK | OK | 16804 ms |

## Fallos detectados

### Q06

- Pregunta: Dime las 5 zonas con más viajes.
- Respuesta: Las 5 zonas con más viajes (acumulado de todo el periodo):

| Puesto | Zona | Distrito | Sede | Viajes |
|--------|------|----------|------|--------|
| 1 | Union Sq | Manhattan | central | 84 |
| 2 | Upper East Side South | Manhattan | central | 81 |
| 3 | Upper West Side South | Manhattan | atocha | 55 |
| 4 | East Village | Manhattan | chamartin | 49 |
| 5 | Financial District North | Manhattan | central | 47 |

*Datos acumulados de todo el periodo histórico (no se pueden filtrar por fechas). 30 zonas con menos de 5 viajes se ocultan por privacidad.*
- Herramientas: `[{'tool': 'get_zones', 'args': {'metric': 'trips', 'n': 5}}]`
- Cifras no respaldadas: `[30.0]`
- Warnings: `[]`

### Q08

- Pregunta: ¿Cuál es el estado actual de la plataforma?
- Respuesta: **Estado de la plataforma (2026-10-04)**

- **Coordinador**: disponible (servido por `central-coordinator:8000`)
- **Réplicas**: 3/3 activas  
  - `central` – activa  
  - `chamartin` – activa  
  - `atocha` – activa
- **Sedes**: las tres responden correctamente
- **Rango de datos**: 2019-12-18 a 2026-10-03
- **Días con datos**: 2019-12-18, 2019-12-31, 2020-01-01, 2026-10-01, 2026-10-03

Todo operativo. ¿En qué métrica o periodo quieres consultar?
- Herramientas: `[{'tool': 'get_platform_status', 'args': {}}]`
- Cifras no respaldadas: `[8000.0]`
- Warnings: `[]`

### Q09

- Pregunta: ¿Cómo fueron los viajes?
- Respuesta: En el periodo completo disponible (18-dic-2019 a 03-oct-2026) se registraron **1 250 viajes** en las tres sedes (central, chamartin, atocha):

- **Ingresos totales:** $24 226.39  
- **Tarifa media (taxímetro):** $13.48  
- **Distancia media:** 3.03 millas  
- **Propina media (solo tarjeta):** $2.19  
- **Importe medio por viaje (con extras, impuestos y propina tarjeta):** $19.38  

¿Quieres ver la evolución por horas/días, comparar sedes o filtrar por un rango de fechas concreto?
- Herramientas: `[{'tool': 'get_kpis', 'args': {}}]`
- Cifras no respaldadas: `[18.0, 3.0]`
- Warnings: `[]`

### Q21

- Pregunta: Muéstrame la evolución diaria de los viajes del 1 al 3 de enero de 2025.
- Respuesta: No hay datos de viajes para el 1‑3 de enero de 2025. Los datos disponibles son de enero de 2020 y los últimos días en tiempo real; no hay información entre ambas fechas.

Si quieres, puedo mostrarte la evolución diaria del último periodo con datos (por ejemplo, los últimos 7 días disponibles). ¿Te interesa?
- Herramientas: `[{'tool': 'get_timeseries', 'args': {'metric': 'trips', 'granularity': 'day', 'date_from': '2025-01-01', 'date_to': '2025-01-03'}}]`
- Cifras no respaldadas: `[7.0]`
- Warnings: `[]`

