# Runbook de integración con la infraestructura de datos

Este documento describe cómo verificar la integración del agente conversacional
con la infraestructura distribuida real de la Parte 2 y cómo comprobar su
comportamiento ante la caída de una sede o de una réplica del coordinador.

Las pruebas de este documento utilizan la infraestructura real. No utilizan el
coordinador mock.

## 1. Preparación

Levantar las tres sedes y las tres réplicas del coordinador desde
`parte2_infraestructura_datos/`:

```bash
make up-all-coordinators
```

Después, desde `parte3_agente_conversacional/`, levantar el chatbot conectado
a los coordinadores reales:

```bash
make chatbot-up
```

Comprobar que la API está disponible:

```bash
curl -s http://localhost:8300/health
```

Y consultar el estado de la plataforma:

```bash
curl -s http://localhost:8300/status | python -m json.tool
```

En condiciones normales deben aparecer:

- las tres réplicas del coordinador activas;
- las sedes `central`, `chamartin` y `atocha` disponibles;
- `central-coordinator` como primera réplica;
- `partial: false`;
- ninguna sede en `sites_failed`.

## 2. Tests de integración

Los tests específicos de integración con la Parte 2 real están en:

```text
tests/test_integration_parte2.py
```

No se ejecutan con el `pytest` normal porque requieren infraestructura real.

Con toda la infraestructura disponible:

```bash
pytest --integration tests/test_integration_parte2.py -v
```

El test del estado normal comprueba que el coordinador devuelve información de
las tres sedes y que la respuesta no es parcial.

Los escenarios que requieren provocar fallos se habilitan mediante
`INTEGRATION_FAILURE_SCENARIO`.

## 3. Consultas representativas

Se han comprobado seis consultas contra los datos reales para cubrir las
principales herramientas del agente:

| Consulta | Herramienta |
|---|---|
| `Compara las tres sedes` | `compare_sites` |
| `¿Cuántos viajes hay en total en todo el periodo disponible?` | `get_kpis` |
| `Muéstrame la evolución diaria de los viajes en todo el periodo disponible` | `get_timeseries` |
| `¿Cómo se reparten los viajes por método de pago en todo el periodo disponible?` | `get_payment_breakdown` |
| `¿Cuáles son las 5 zonas de recogida con más viajes en todo el periodo disponible?` | `get_zones` |
| `¿Cuál es el estado actual de la plataforma?` | `get_platform_status` |

En condiciones normales, las consultas deben indicar las tres sedes en
`sites_ok`, ninguna en `sites_failed` y `partial: false`.

## 4. Caída de una sede

Para simular la indisponibilidad de Atocha se detiene únicamente su `site_api`,
manteniendo disponible su réplica del coordinador y el resto de su
infraestructura.

Desde `parte2_infraestructura_datos/`:

```bash
docker compose -p atocha \
  --env-file sites/atocha.env \
  -f deploy/docker-compose.site.yml \
  stop site_api
```

Ejecutar el escenario de integración desde `parte3_agente_conversacional/`:

```bash
INTEGRATION_FAILURE_SCENARIO=site_down \
pytest --integration tests/test_integration_parte2.py -v
```

La respuesta debe indicar:

```text
sites_ok     = central, chamartin
sites_failed = atocha
partial      = true
```

También puede comprobarse a través del chatbot:

```bash
curl -s http://localhost:8300/chat \
  -H "Content-Type: application/json" \
  -d '{"session_id":"integration-site-down","message":"Compara las tres sedes"}' \
  | python -m json.tool
```

El chatbot debe seguir respondiendo, pero debe avisar de que el resultado es
parcial y nombrar explícitamente a `atocha` como sede no disponible.

Restaurar la sede:

```bash
docker compose -p atocha \
  --env-file sites/atocha.env \
  -f deploy/docker-compose.site.yml \
  up -d site_api
```

## 5. Failover del coordinador

Para comprobar el failover se detiene únicamente la réplica del coordinador
Central desde `parte2_infraestructura_datos/`:

```bash
make stop-coordinator SITE=central
```

Las APIs de las tres sedes permanecen disponibles. Solo desaparece la primera
réplica de la lista de coordinadores.

Ejecutar el escenario:

```bash
INTEGRATION_FAILURE_SCENARIO=coordinator_failover \
pytest --integration tests/test_integration_parte2.py -v
```

El cliente debe intentar primero el coordinador Central y, al no estar
disponible, continuar con Chamartín.

Desde el host, las URLs utilizadas por el cliente son:

```text
Central    -> http://localhost:8100
Chamartín  -> http://localhost:8101
Atocha     -> http://localhost:8102
```

Por tanto, en este escenario `served_by` debe corresponder a Chamartín y el
intento fallido contra Central debe aparecer en `skipped`.

La caída de la réplica Central no supone la pérdida de la sede Central, por lo
que las tres sedes deben continuar en `sites_ok` y la respuesta debe mantener
`partial: false`.

El estado del chatbot también puede comprobarse con:

```bash
curl -s http://localhost:8300/status | python -m json.tool
```

Debe mostrar dos de las tres réplicas activas y Chamartín como réplica que
atiende la petición.

Restaurar el coordinador Central:

```bash
make up-coordinator SITE=central
```

## 6. Verificación final

Después de restaurar la infraestructura:

```bash
curl -s http://localhost:8300/status | python -m json.tool
```

Las tres réplicas y las tres sedes deben volver a estar disponibles.

Finalmente, ejecutar la suite de tests normal:

```bash
pytest
```

Los tests de integración deben quedar omitidos en esta ejecución, ya que solo
se habilitan mediante `--integration`.

## 7. Evidencias

Las evidencias de ejecución de estos escenarios se almacenan en:

```text
evidence/integration/
```

Incluyen la ejecución contra la infraestructura completa, la respuesta parcial
con una sede caída y el failover tras la caída de la réplica primaria del
coordinador.
