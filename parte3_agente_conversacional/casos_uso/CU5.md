# CU5 · Tolerancia a fallos

## Objetivo

Demostrar que el chatbot sigue respondiendo cuando parte de la infraestructura
de datos deja de estar disponible.

Este caso de uso cubre dos escenarios distintos:

- caída de una sede;
- caída del coordinador principal de Central y uso del failover.

El agente debe mantener la respuesta siempre que existan datos disponibles y
debe informar claramente cuando el resultado sea parcial.

## Actor

Usuario de la plataforma que realiza una consulta mientras parte de la
infraestructura distribuida está caída.

## Precondiciones

- La API del agente está levantada.
- La interfaz Streamlit está disponible.
- Existe una clave válida de OpenRouter.
- El chatbot está conectado al mock o a la infraestructura real de la parte 2.
- Las consultas realizadas requieren datos de varias sedes o el acceso al
  coordinador.

## Escenario 1 · Sede caída

### Diálogo de ejemplo

**Usuario**

> Compara las tres sedes.

**Asistente**

Si, por ejemplo, Atocha está caída, el agente debe responder utilizando los
datos disponibles de `central` y `chamartin`.

La respuesta debe indicar expresamente que Atocha no ha respondido y que el
resultado es parcial.

No debe presentar los datos disponibles como si representaran correctamente a
las tres sedes.

## Herramientas implicadas

Para demostrar la caída de una sede puede utilizarse una herramienta que
consulte varias sedes, por ejemplo:

### `compare_sites`

Permite comparar los valores disponibles entre las sedes solicitadas.

Si una sede no responde, la salida de la herramienta contiene información de
parcialidad que el agente debe trasladar a la respuesta.

También puede observarse el mismo comportamiento con herramientas como:

- `get_kpis`;
- `get_timeseries`.

## Información de trazabilidad

Las respuestas de las herramientas incluyen información sobre:

- sedes que han respondido;
- sedes que han fallado;
- si el resultado es parcial;
- coordinador que ha servido la petición.

Esta información se incorpora a `sources` y se muestra en la interfaz dentro
del desplegable de trazabilidad.

## Demostración con el mock

El mock permite simular fácilmente una sede caída.

Desde `parte3_agente_conversacional/`:

```bash
make chatbot-down
make chatbot-mock DOWN_SITES=atocha
```

Después puede realizarse desde la interfaz una consulta como:

> Compara las tres sedes.

La respuesta debe mostrar el aviso correspondiente a la ausencia de Atocha.

## Escenario 2 · Failover del coordinador

La capa de datos dispone de varios coordinadores configurados en este orden:

1. `central-coordinator`;
2. `chamartin-coordinator`;
3. `atocha-coordinator`.

Si el primero no responde, el cliente intenta automáticamente el siguiente
coordinador disponible.

### Diálogo de ejemplo

**Usuario**

> ¿Cuántos viajes hubo el 1 de octubre de 2026?

**Asistente**

El usuario recibe una respuesta normal aunque el coordinador principal de
Central esté caído, siempre que otra réplica del coordinador pueda servir la
consulta.

El failover es transparente para el usuario, aunque puede comprobarse en la
trazabilidad de la respuesta mediante el campo `served_by`.

## Endpoints implicados

### API del agente

```text
POST /chat
```

La interfaz continúa utilizando el mismo endpoint independientemente del fallo
de la infraestructura.

### Estado de la plataforma

```text
GET /status
```

La interfaz puede consultar el estado de las sedes y coordinadores y mostrarlo
en la barra lateral.

## Flujo · sede caída

1. El usuario realiza una consulta que requiere varias sedes.
2. La interfaz envía la pregunta mediante `POST /chat`.
3. El agente selecciona la herramienta adecuada.
4. La herramienta realiza la consulta a través de la capa de datos.
5. Una de las sedes no responde.
6. Se devuelven los datos disponibles junto con información de parcialidad.
7. El agente redacta la respuesta indicando qué sede falta.
8. La interfaz muestra un aviso y la trazabilidad del fallo.

## Flujo · failover del coordinador

1. El usuario realiza una consulta.
2. El agente intenta acceder al primer coordinador configurado.
3. El coordinador de Central no responde.
4. La capa de datos prueba automáticamente el siguiente coordinador.
5. Otro coordinador sirve la consulta.
6. El agente recibe los datos y responde normalmente.
7. La trazabilidad permite comprobar qué coordinador sirvió finalmente la
   petición.

## Qué demuestra

Este caso de uso demuestra:

- tolerancia a la caída de una sede;
- resultados parciales correctamente identificados;
- avisos claros al usuario;
- failover automático entre coordinadores;
- desacoplamiento entre el chatbot y una réplica concreta del coordinador;
- trazabilidad de los fallos;
- integración con la arquitectura distribuida de la parte 2.

## Casos límite

### Caída de una sede no solicitada

Si el usuario consulta únicamente una sede que está disponible, la caída de
otra sede no debería afectar al resultado.

### Caída de la única sede solicitada

Si el usuario consulta exclusivamente una sede que no responde, el agente no
debe inventar datos.

Debe explicar que no ha podido obtener información de esa sede.

### Varias sedes caídas

Si solo responde una parte de las sedes solicitadas, el agente debe indicar
todas las que faltan y dejar claro que el resultado es parcial.

### Todas las sedes caídas

Si no existe ninguna fuente de datos disponible, el agente debe informar del
problema y no generar cifras.

### Caída de varios coordinadores

La capa de datos debe recorrer los coordinadores configurados en orden hasta
encontrar uno disponible.

Si ninguno responde, la consulta no puede completarse y el usuario debe recibir
un mensaje de error comprensible.

## Captura

La captura correspondiente a este caso de uso se guarda en:

```text
casos_uso/capturas/CU5.png
```

La captura debe mostrar preferiblemente el escenario de **Atocha caída** e
incluir:

- la pregunta del usuario;
- la respuesta parcial;
- el aviso visible de que Atocha no está disponible;
- los datos de las sedes que sí han respondido;
- el desplegable de trazabilidad mostrando `sites_failed` o la información
  equivalente.

El escenario de failover del coordinador se demostrará además en el vídeo de
la entrega.
