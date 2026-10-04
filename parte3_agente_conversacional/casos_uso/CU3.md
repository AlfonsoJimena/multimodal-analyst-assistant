# CU3 · Evolución temporal y hora punta

## Objetivo

Permitir al usuario analizar cómo evoluciona una métrica a lo largo del tiempo
y detectar el momento de mayor actividad dentro del periodo consultado.

El agente debe interpretar una petición temporal, seleccionar la granularidad
adecuada y devolver una serie temporal respaldada por los datos de la
infraestructura.

## Actor

Usuario de la plataforma que quiere estudiar la evolución de los viajes,
ingresos u otras métricas agregadas a lo largo del tiempo.

## Precondiciones

- La API del agente está levantada.
- La interfaz Streamlit está disponible.
- El chatbot está conectado al coordinador mock o a los coordinadores de la
  parte 2.
- Existe una clave válida de OpenRouter para utilizar el LLM.
- El periodo consultado contiene datos.

## Diálogo de ejemplo

**Usuario**

> ¿Cómo evolucionaron los viajes entre el 1 y el 3 de octubre de 2026 y cuál fue el día con más viajes?

**Asistente**

El agente obtiene la serie temporal de viajes para el periodo solicitado y
muestra su evolución por día.

Además, identifica el punto máximo de la serie y señala qué día registró el
mayor número de viajes.

## Herramientas implicadas

### `get_timeseries`

Obtiene una serie temporal para una métrica concreta.

Puede utilizarse para analizar, entre otras:

- número de viajes;
- ingresos.

Admite parámetros como:

- sede o conjunto de sedes;
- fecha inicial;
- fecha final;
- métrica;
- granularidad temporal.

La granularidad puede ser, según la consulta:

- `day`, para evolución diaria;
- `hour`, para evolución horaria.

La herramienta devuelve también información suficiente para identificar el
máximo de la serie.

## Endpoints implicados

### API del agente

```text
POST /chat
```

La interfaz envía la pregunta en lenguaje natural al agente.

### Coordinador de datos

La herramienta `get_timeseries` consulta los agregados temporales de la
infraestructura de la parte 2 a través de la capa de datos del agente.

## Flujo

1. El usuario realiza una pregunta sobre evolución temporal.
2. La interfaz envía la consulta mediante `POST /chat`.
3. El LLM selecciona `get_timeseries`.
4. El agente identifica la métrica, el periodo y la granularidad.
5. La herramienta consulta al coordinador.
6. El coordinador devuelve la serie temporal agregada.
7. El agente identifica el máximo de la serie.
8. El LLM redacta la respuesta utilizando exclusivamente los valores
   proporcionados por la herramienta.
9. La interfaz representa la evolución mediante un gráfico de líneas.

## Qué demuestra

Este caso de uso demuestra:

- interpretación de preguntas temporales;
- selección automática de granularidad;
- uso de series temporales agregadas;
- representación mediante gráfico de líneas;
- identificación del máximo de una serie;
- integración entre el agente y los agregados temporales de la parte 2;
- trazabilidad de los datos utilizados.

## Casos límite

### No se especifica granularidad

Ejemplo:

> ¿Cómo evolucionaron los viajes entre el 1 y el 3 de octubre de 2026?

El agente debe escoger una granularidad razonable según el periodo consultado.
Para varios días puede utilizar granularidad diaria.

### Consulta de hora punta

Ejemplo:

> ¿Cuál fue la hora con más viajes el 1 de octubre de 2026?

El agente debe utilizar una serie con granularidad `hour` y señalar la hora que
presenta el máximo valor.

### Fecha sin datos

Ejemplo:

> ¿Cómo evolucionaron los viajes del 1 al 3 de enero de 2025?

El agente no debe inventar una serie ni rellenar valores inexistentes. Debe
informar de que no hay datos disponibles para ese periodo.

### Valores ocultos por privacidad

Algunas celdas temporales pueden estar ocultas si contienen menos de
`MIN_TRIPS_PER_CELL` viajes.

La interfaz puede mostrar esos puntos como huecos en la serie y el agente no
debe reconstruir ni estimar los valores ocultos.

### Sede caída

Si alguna sede solicitada no responde, la serie puede ser parcial. El agente
debe informar de ello e indicar qué sede no está disponible.

Este comportamiento se muestra de forma específica en el CU5.

## Captura

La captura correspondiente a este caso de uso se guarda en:

```text
casos_uso/capturas/CU3.png
```

La captura debe mostrar:

- la pregunta del usuario;
- la respuesta del agente;
- el gráfico de líneas con la evolución temporal;
- el máximo identificado en la respuesta;
- el desplegable de trazabilidad con la herramienta `get_timeseries`.
