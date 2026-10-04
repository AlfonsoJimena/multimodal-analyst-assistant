# CU1 · KPIs de una sede o un periodo

## Objetivo

Permitir al usuario consultar los principales indicadores de los viajes de taxi
para una sede concreta, varias sedes o un intervalo temporal.

El agente debe interpretar la pregunta en lenguaje natural, seleccionar la
herramienta adecuada y devolver únicamente cifras obtenidas de la
infraestructura de datos.

## Actor

Usuario de la plataforma que quiere consultar indicadores agregados sobre los
viajes de taxi.

## Precondiciones

- La API del agente está levantada.
- La interfaz Streamlit está disponible.
- El chatbot está conectado al coordinador mock o a los coordinadores de la
  parte 2.
- Existe una clave válida de OpenRouter para utilizar el LLM.
- El periodo consultado contiene datos.

## Diálogo de ejemplo

**Usuario**

> ¿Cuántos viajes hubo en Central el 1 de enero de 2020?

**Asistente**

El agente consulta los KPIs de la sede `central` para el periodo solicitado y
responde con el número de viajes correspondiente.

La respuesta puede incluir además otros indicadores disponibles para ese
periodo, como ingresos, distancia media o importe medio, siempre que procedan
de la herramienta ejecutada.

## Herramientas implicadas

### `get_kpis`

Obtiene los principales indicadores agregados:

- número de viajes;
- ingresos;
- distancia media;
- importe medio;
- otras métricas agregadas disponibles en el coordinador.

Admite filtros por:

- sede;
- fecha inicial;
- fecha final.

## Endpoints implicados

### API del agente

```text
POST /chat
```

La interfaz envía la pregunta en lenguaje natural al agente.

### Coordinador de datos

La herramienta `get_kpis` consulta los datos agregados de la infraestructura de
la parte 2 a través de la capa de datos del agente.

El acceso al coordinador nunca se realiza directamente desde la interfaz.

## Flujo

1. El usuario escribe una pregunta sobre KPIs.
2. La interfaz envía la pregunta mediante `POST /chat`.
3. El LLM selecciona `get_kpis`.
4. El agente valida los parámetros de sede y fechas.
5. La herramienta consulta al coordinador.
6. El resultado agregado vuelve al agente.
7. El LLM redacta la respuesta utilizando únicamente las cifras devueltas por
   la herramienta.
8. La interfaz muestra la respuesta y la trazabilidad de la consulta.

## Qué demuestra

Este caso de uso demuestra:

- interpretación de lenguaje natural;
- selección automática de herramientas;
- filtrado por sede y fechas;
- integración entre interfaz, agente y parte 2;
- uso de datos reales sin generar cifras desde el LLM;
- trazabilidad mediante `sources`;
- presentación de KPIs en la interfaz.

## Casos límite

### Pregunta sin sede

Ejemplo:

> ¿Cuántos viajes hubo el 1 de enero de 2020?

El agente puede consultar las tres sedes y debe indicar el ámbito utilizado en
la respuesta.

### Pregunta sin fecha

Ejemplo:

> ¿Cuántos viajes hubo en Central?

El agente utiliza un criterio razonable para el periodo o consulta primero el
estado de la plataforma si necesita conocer qué fechas tienen datos.

### Fecha sin datos

Ejemplo:

> ¿Cuántos viajes hubo el 10 de mayo de 2025?

El agente no debe inventar cifras. Debe informar de que no hay datos
disponibles para ese periodo.

### Sede inexistente

Ejemplo:

> ¿Cuántos viajes hubo en Barcelona?

El agente debe indicar que esa sede no forma parte de la plataforma.

## Captura

La captura correspondiente a este caso de uso se guarda en:

```text
casos_uso/capturas/CU1.png
```

La captura debe mostrar:

- la pregunta del usuario;
- la respuesta del agente;
- los KPIs mostrados por la interfaz;
- el desplegable de trazabilidad con la herramienta `get_kpis`.
