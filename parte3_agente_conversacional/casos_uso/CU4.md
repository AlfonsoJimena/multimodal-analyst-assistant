# CU4 · Métodos de pago y zonas

## Objetivo

Permitir al usuario consultar cómo se distribuyen los viajes o los ingresos por
método de pago y analizar las zonas de recogida con mayor actividad.

Este caso de uso demuestra que el agente puede responder preguntas sobre
dimensiones distintas de las sedes y del tiempo, utilizando agregados
específicos de la parte 2.

## Actor

Usuario de la plataforma que quiere analizar la distribución de los viajes por
método de pago o por zona de recogida.

## Precondiciones

- La API del agente está levantada.
- La interfaz Streamlit está disponible.
- El chatbot está conectado al coordinador mock o a los coordinadores de la
  parte 2.
- Existe una clave válida de OpenRouter para utilizar el LLM.
- Los agregados de pagos y zonas están disponibles.

## Diálogo de ejemplo

### Métodos de pago

**Usuario**

> ¿Qué métodos de pago se utilizan más?

**Asistente**

El agente consulta el desglose agregado por método de pago y muestra la
distribución de los viajes entre las distintas categorías disponibles.

La respuesta puede incluir el número de viajes, ingresos y porcentaje
correspondiente a cada método.

### Zonas

**Usuario**

> ¿Cuáles son las cinco zonas con más viajes?

**Asistente**

El agente consulta el ranking de zonas de recogida y devuelve las zonas con
mayor número de viajes.

Los identificadores de zona se enriquecen con el nombre y el distrito usando la
base de conocimiento incluida en `src/knowledge/`.

## Herramientas implicadas

### `get_payment_breakdown`

Obtiene el desglose agregado por método de pago.

Puede devolver información como:

- número de viajes;
- ingresos;
- porcentaje sobre el total.

Los códigos de pago se traducen a nombres comprensibles mediante la base de
conocimiento del agente.

### `get_zones`

Obtiene un ranking de zonas de recogida para una métrica concreta.

Puede utilizarse para consultar, entre otras:

- zonas con más viajes;
- zonas con más ingresos.

Los resultados incluyen el identificador de zona junto con su nombre y
distrito.

### `get_zone`

Obtiene las métricas agregadas de una zona concreta.

La zona puede indicarse por:

- identificador;
- nombre.

Por ejemplo:

> ¿Cuántos viajes salen de JFK Airport?

## Endpoints implicados

### API del agente

```text
POST /chat
```

La interfaz envía las preguntas en lenguaje natural al agente.

### Coordinador de datos

Las herramientas `get_payment_breakdown`, `get_zones` y `get_zone` consultan
los agregados correspondientes a través de la capa de datos del agente.

## Flujo

1. El usuario pregunta por métodos de pago o zonas.
2. La interfaz envía la pregunta mediante `POST /chat`.
3. El LLM selecciona la herramienta adecuada.
4. El agente valida los parámetros de la consulta.
5. La herramienta consulta los agregados de la parte 2.
6. En las consultas de zonas, el agente añade el nombre y distrito asociados al
   identificador de zona.
7. El LLM redacta la respuesta utilizando exclusivamente los resultados de la
   herramienta.
8. La interfaz representa los datos mediante tablas, gráficos o KPIs.

## Qué demuestra

Este caso de uso demuestra:

- selección entre distintas herramientas según la intención del usuario;
- análisis de datos por método de pago;
- análisis de zonas de recogida;
- uso de una base de conocimiento externa para traducir identificadores de
  zona;
- visualización mediante tablas y gráficos;
- aplicación de las reglas de privacidad;
- trazabilidad de las fuentes utilizadas.

## Casos límite

### Consulta con fecha sobre métodos de pago

Ejemplo:

> ¿Qué método de pago se utilizó más ayer?

Los agregados de métodos de pago son acumulados y no disponen de dimensión
temporal.

El agente no debe presentar el resultado acumulado como si correspondiera a
ayer. Debe explicar la limitación y ofrecer el desglose disponible para todo el
periodo.

### Consulta con fecha sobre zonas

Ejemplo:

> ¿Cuáles fueron las zonas con más viajes el 1 de octubre de 2026?

Los agregados de zonas son acumulados y no pueden filtrarse por fecha.

El agente debe indicarlo claramente y ofrecer el ranking disponible para el
periodo completo.

### Zona inexistente

Ejemplo:

> ¿Cuántos viajes salen de una zona llamada Aeropuerto de Barcelona?

Si la zona no existe en la tabla de zonas de NYC, el agente no debe inventar
una correspondencia.

### Zona con pocos viajes

Las zonas con menos de `MIN_TRIPS_PER_CELL` viajes pueden quedar ocultas por
privacidad.

El agente no debe estimar ni reconstruir esos valores.

### Número de resultados

Ejemplo:

> Dame las cinco zonas con más viajes.

El agente debe respetar, cuando sea posible, el número de resultados solicitado
por el usuario y no añadir zonas adicionales sin necesidad.

## Captura

La captura correspondiente a este caso de uso se guarda en:

```text
casos_uso/capturas/CU4.png
```

La captura debe mostrar al menos una consulta representativa de este caso de
uso.

Preferiblemente debe mostrar:

- una pregunta sobre métodos de pago o zonas;
- la respuesta del agente;
- la tabla o gráfico generado;
- los nombres de las categorías o zonas;
- el desplegable de trazabilidad con la herramienta utilizada.
