# CU2 · Comparativa entre sedes

## Objetivo

Permitir al usuario comparar los principales indicadores de las distintas
sedes de la plataforma.

El agente debe interpretar una petición comparativa en lenguaje natural,
seleccionar la herramienta adecuada y devolver los resultados separados por
sede para facilitar su comparación.

## Actor

Usuario de la plataforma que quiere comparar el comportamiento de las sedes
`central`, `chamartin` y `atocha`.

## Precondiciones

- La API del agente está levantada.
- La interfaz Streamlit está disponible.
- El chatbot está conectado al coordinador mock o a los coordinadores de la
  parte 2.
- Existe una clave válida de OpenRouter para utilizar el LLM.
- Las sedes consultadas contienen datos para el periodo solicitado.

## Diálogo de ejemplo

**Usuario**

> Compara las tres sedes el 1 de octubre de 2026.

**Asistente**

El agente consulta los datos agregados de las tres sedes para el periodo
solicitado y devuelve una comparación entre `central`, `chamartin` y `atocha`.

La respuesta puede mostrar métricas como el número de viajes o los ingresos de
cada sede, acompañadas de una tabla o gráfico que facilite la comparación.

## Herramientas implicadas

### `compare_sites`

Compara una métrica entre varias sedes.

Puede utilizarse para consultar, entre otras:

- número de viajes;
- ingresos;
- distancia media;
- importe medio.

Admite filtros por:

- conjunto de sedes;
- fecha inicial;
- fecha final;
- métrica a comparar.

## Endpoints implicados

### API del agente

```text
POST /chat
```

La interfaz envía la pregunta en lenguaje natural al agente.

### Coordinador de datos

La herramienta `compare_sites` consulta los datos agregados de la
infraestructura de la parte 2 a través de la capa de datos del agente.

El coordinador devuelve la información necesaria para separar los resultados
por sede.

## Flujo

1. El usuario solicita una comparación entre sedes.
2. La interfaz envía la pregunta mediante `POST /chat`.
3. El LLM selecciona `compare_sites`.
4. El agente identifica las sedes, la métrica y el periodo solicitado.
5. La herramienta consulta al coordinador.
6. El resultado vuelve separado por sede.
7. El LLM redacta la comparación utilizando únicamente las cifras devueltas por
   la herramienta.
8. La interfaz muestra la respuesta junto con la tabla o gráfico comparativo y
   la trazabilidad.

## Qué demuestra

Este caso de uso demuestra:

- interpretación de preguntas comparativas en lenguaje natural;
- uso de una herramienta específica para comparar sedes;
- integración con el despliegue distribuido de la parte 2;
- obtención de resultados separados por sede;
- visualización mediante tabla y gráfico;
- trazabilidad de la consulta;
- uso exclusivo de cifras procedentes de las herramientas.

## Casos límite

### No se especifican las sedes

Ejemplo:

> Compara las sedes el 1 de octubre de 2026.

El agente puede utilizar por defecto las tres sedes disponibles:
`central`, `chamartin` y `atocha`, e indicar ese criterio en la respuesta.

### Se solicita una única sede

Ejemplo:

> Compara Central el 1 de octubre de 2026.

Al no existir realmente una comparación entre varias sedes, el agente puede
responder con los datos de esa sede o utilizar una herramienta más adecuada
como `get_kpis`.

### Sede inexistente

Ejemplo:

> Compara Central con Barcelona.

El agente debe indicar que Barcelona no es una sede válida de la plataforma y
no debe inventar datos para ella.

### Fecha sin datos

Ejemplo:

> Compara las tres sedes el 15 de junio de 2024.

El agente no debe inventar cifras. Debe informar de que no existen datos
disponibles para ese periodo.

### Una sede no responde

Si una de las sedes está caída, el agente debe utilizar los datos disponibles
de las demás sedes y avisar claramente de que la comparación es parcial,
indicando qué sede falta.

Este escenario se muestra de forma específica en el CU5.

## Captura

La captura correspondiente a este caso de uso se guarda en:

```text
casos_uso/capturas/CU2.png
```

La captura debe mostrar:

- la pregunta del usuario;
- la respuesta comparativa del agente;
- la tabla o gráfico con los resultados por sede;
- el desplegable de trazabilidad con la herramienta `compare_sites`.
