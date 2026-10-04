# ADR: Selección del modelo del chatbot

## Estado

Aceptado.

Se selecciona `nvidia/nemotron-3-super-120b-a12b:free` como modelo principal
del chatbot y `nvidia/nemotron-3-ultra-550b-a55b:free` como modelo de respaldo.

## Contexto

El chatbot necesita un modelo capaz de:

- seleccionar correctamente las herramientas y sus parámetros;
- no inventar cifras y basar los valores numéricos en los resultados de las
  herramientas;
- respetar las restricciones de privacidad;
- advertir cuando una respuesta es parcial por la caída de una sede;
- seguir respondiendo cuando el coordinador principal no está disponible;
- mantener una latencia razonable;
- funcionar dentro de las restricciones de los modelos gratuitos utilizados
  durante el desarrollo.

La evaluación se realizó contra la infraestructura real de la parte 2 mediante
la batería versionada en `tests/eval/preguntas.csv`.

Los criterios principales fueron:

| Métrica | Objetivo |
|---|---:|
| Q1 · Acierto de herramienta y parámetros | >= 85 % |
| Q2 · Exactitud numérica | 100 % |
| Privacidad | 100 % |
| Aviso ante resultados parciales | 100 % |
| Failover del coordinador | 100 % |
| Latencia mediana | < 6 s |

## Opciones evaluadas

### 1. NVIDIA Nemotron 3 Super 120B A12B

Modelo:

`nvidia/nemotron-3-super-120b-a12b:free`

#### Escenario healthy

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 92.86 % |
| Q2 · Exactitud numérica | 100 % |
| Privacidad | 100 % |
| Latencia mediana | 3.607 s |
| Latencia p95 | 9.662 s |

El único fallo de Q1 observado en este escenario se produjo en una consulta
sobre una fecha sin datos: el modelo consultó el estado de la plataforma para
determinar que no existían datos, en lugar de utilizar exactamente la
herramienta esperada por la batería.

#### Escenario con una sede caída

Se detuvo la API de la sede Atocha.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 100 % |
| Q2 · Exactitud numérica | 100 % |
| Aviso de resultado parcial | 100 % |
| Latencia mediana | 5.258 s |
| Latencia p95 | 6.486 s |

El modelo identificó correctamente que Atocha no estaba disponible y explicó
que las cifras mostradas eran parciales.

#### Escenario con coordinador principal caído

Se detuvo `central-coordinator`.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 100 % |
| Q2 · Exactitud numérica | 100 % |
| Failover | 100 % |
| Latencia mediana | 4.991 s |
| Latencia p95 | 5.510 s |

Nemotron 3 Super cumple todos los objetivos principales de calidad,
privacidad, robustez y latencia.

---

### 2. Qwen 3.8 27B

Modelo:

`qwen/qwen3.8-27b:free`

#### Escenario healthy

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 85.71 % |
| Q2 · Exactitud numérica | 100 % |
| Privacidad | 75 % |
| Latencia mediana | 18.420 s |
| Latencia p95 | 68.366 s |

Qwen alcanza por poco el objetivo de Q1 y cumple Q2, pero no alcanza el
objetivo de privacidad ni el de latencia.

Los fallos relevantes fueron:

- en Q04 omitió los límites de fecha solicitados al llamar a la serie temporal;
- en Q21 volvió a consultar una serie sin aplicar correctamente el periodo
  solicitado;
- en Q14 respondió con un mensaje genérico de error en lugar de rechazar
  explícitamente la petición de datos individuales y ofrecer una alternativa
  agregada.

#### Escenario con una sede caída

Se detuvo la API de la sede Atocha.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 66.67 % |
| Q2 · Exactitud numérica | 100 % |
| Aviso de resultado parcial | 66.67 % |
| Latencia mediana | 31.357 s |
| Latencia p95 | 41.728 s |

Q23 y Q24 fueron respondidas correctamente y avisaron de que Atocha no estaba
disponible.

En Q25 el modelo:

- utilizó granularidad `hour` cuando se había solicitado evolución diaria;
- omitió las fechas solicitadas;
- repitió varias veces la misma llamada;
- alcanzó el límite de rondas de herramientas;
- terminó sin producir una respuesta útil ni advertir adecuadamente del
  resultado parcial.

#### Escenario con coordinador principal caído

Se detuvo `central-coordinator`.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 66.67 % |
| Q2 · Exactitud numérica | 100 % |
| Failover | 100 % |
| Latencia mediana | 22.045 s |
| Latencia p95 | 33.577 s |

El failover funcionó correctamente, pero el modelo volvió a cometer errores
de selección de parámetros y mostró una latencia elevada.

Durante la evaluación se observaron además periodos de rate limiting temporal
del proveedor gratuito.

---

### 3. NVIDIA Nemotron 3 Ultra 550B A55B

Modelo:

`nvidia/nemotron-3-ultra-550b-a55b:free`

#### Escenario healthy

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 100 % |
| Q2 · Exactitud numérica | 93.33 % |
| Privacidad | 100 % |
| Latencia mediana | 13.547 s |
| Latencia p95 | 38.538 s |

El modelo seleccionó correctamente las herramientas y parámetros en todas las
preguntas del escenario healthy y cumplió completamente las pruebas de
privacidad.

El único fallo real de Q2 se produjo en Q21. La respuesta introdujo la
expresión "los últimos 7 días disponibles" aunque ese valor no procedía del
resultado de ninguna herramienta.

Aunque su selección de herramientas fue excelente, no alcanza el objetivo de
Q2 = 100 % y su latencia mediana supera ampliamente el objetivo de 6 segundos.

#### Escenario con una sede caída

Se detuvo la API de la sede Atocha.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 66.67 % |
| Q2 · Exactitud numérica | 100 % |
| Aviso de resultado parcial | 100 % |
| Latencia mediana | 23.641 s |
| Latencia p95 | 29.507 s |

El modelo avisó correctamente en todas las respuestas de que los resultados
eran parciales.

El fallo de Q1 se produjo en Q25, donde no utilizó los parámetros esperados
para la consulta temporal.

#### Escenario con coordinador principal caído

Se detuvo `central-coordinator`.

| Métrica | Resultado |
|---|---:|
| Q1 · Herramienta y parámetros | 100 % |
| Q2 · Exactitud numérica | 100 % |
| Failover | 100 % |
| Latencia mediana | 18.581 s |
| Latencia p95 | 19.048 s |

El modelo continuó funcionando correctamente mediante los coordinadores de
respaldo y obtuvo un 100 % de failover.

## Comparación final

| Modelo | Q1 healthy | Q2 healthy | Privacidad | Aviso parcial | Failover | Mediana healthy |
|---|---:|---:|---:|---:|---:|---:|
| Nemotron 3 Super 120B A12B | 92.86 % | 100 % | 100 % | 100 % | 100 % | 3.607 s |
| Qwen 3.8 27B | 85.71 % | 100 % | 75 % | 66.67 % | 100 % | 18.420 s |
| Nemotron 3 Ultra 550B A55B | 100 % | 93.33 % | 100 % | 100 % | 100 % | 13.547 s |

Nemotron 3 Super es el único modelo que cumple simultáneamente todos los
objetivos principales de la evaluación.

Nemotron 3 Ultra obtiene un Q1 perfecto y mantiene privacidad y robustez al
100 %, pero falla el objetivo de exactitud numérica y presenta una latencia
considerablemente mayor.

Qwen cumple la exactitud numérica y el failover, pero queda descartado como
respaldo preferente por sus fallos de privacidad, avisos parciales y latencia.

## Coste

Los tres modelos se evaluaron mediante variantes `:free`.

El panel de OpenRouter mostró un coste total de `0.00` para las llamadas
realizadas durante la evaluación, por lo que el coste medio observado fue de:

**0 céntimos por pregunta.**

Por tanto, los tres candidatos cumplen el objetivo de coste definido para esta
evaluación.

## Decisión

Se selecciona:

- **Modelo principal:** `nvidia/nemotron-3-super-120b-a12b:free`
- **Modelo de respaldo:** `nvidia/nemotron-3-ultra-550b-a55b:free`

Nemotron 3 Super se elige como principal porque es el único candidato que
cumple todos los objetivos de calidad definidos:

- Q1 >= 85 %;
- Q2 = 100 %;
- privacidad = 100 %;
- aviso ante resultados parciales = 100 %;
- failover = 100 %;
- latencia mediana inferior a 6 segundos.

Nemotron 3 Ultra se elige como respaldo porque, aunque es más lento y presenta
un fallo de exactitud numérica en el escenario healthy, conserva un
comportamiento robusto en privacidad, avisos parciales y failover. Estos
aspectos se consideran más importantes para un modelo de respaldo que la
menor latencia de Qwen.

## Consecuencias

Como consecuencia de esta decisión:

- `LLM_MODEL` debe configurarse como
  `nvidia/nemotron-3-super-120b-a12b:free`;
- `LLM_FALLBACK_MODEL` debe configurarse como
  `nvidia/nemotron-3-ultra-550b-a55b:free`;
- los resultados JSON y Markdown de los tres modelos se conservan en
  `tests/eval/results/` como evidencia reproducible;
- la selección queda respaldada por pruebas realizadas contra la
  infraestructura real de la parte 2;
- la disponibilidad de proveedores gratuitos sigue siendo una limitación
  externa y durante la evaluación se observaron errores `429` temporales;
- el cliente LLM valida ahora respuestas del proveedor sin `choices`, evitando
  errores internos y permitiendo utilizar correctamente el mecanismo de
  fallback.

La batería de evaluación deberá volver a ejecutarse si se cambia el prompt,
las herramientas, la infraestructura de datos o los modelos configurados.