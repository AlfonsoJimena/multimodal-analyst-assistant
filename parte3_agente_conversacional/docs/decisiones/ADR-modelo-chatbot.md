# ADR — Modelo del chatbot

## Contexto

La Parte 3 requiere seleccionar un modelo de lenguaje para el agente conversacional a partir de una evaluación reproducible con preguntas representativas del dominio.

La evaluación mide:

- precisión en selección de herramienta y parámetros;
- fidelidad numérica respecto a los resultados de las herramientas;
- robustez ante caída de una sede;
- robustez ante caída del coordinador principal;
- rechazo de solicitudes que vulneran la política de privacidad;
- latencia;
- coste medio por pregunta.

La batería está definida en `tests/eval/preguntas.csv` y se ejecuta con:

```bash
python -m tests.eval.run_eval --model <model-id>
```

## Opciones evaluadas

### `nvidia/nemotron-3-super-120b-a12b:free`

Modelo principal seleccionado inicialmente en P3-08.

**Resultados finales:** pendientes de completar.

### `qwen/qwen3.8-27b:free`

Modelo de familia distinta usado como fallback en P3-08.

**Resultados finales:** pendientes de completar.

### `google/gemma-4-31b-it:free`

Tercer candidato de evaluación, perteneciente a una familia distinta de los otros dos modelos.
Está disponible gratuitamente en OpenRouter y soporta function calling mediante `tools`.


**Resultados finales:** pendientes de completar.

## Resultados

| Modelo        | Q1 tool accuracy | Q2 numeric accuracy | Privacidad | Sede caída | Failover coordinador | Mediana latencia | p95       | Coste medio |
| ------------- | ---------------- | ------------------- | ---------- | ---------- | -------------------- | ---------------- | --------- | ----------- |
| Nemotron      | pendiente        | pendiente           | pendiente  | pendiente  | pendiente            | pendiente        | pendiente | pendiente   |
| Qwen          | pendiente        | pendiente           | pendiente  | pendiente  | pendiente            | pendiente        | pendiente | pendiente   |
| Gemma 4 31B   | pendiente        | pendiente           | pendiente  | pendiente  | pendiente            | pendiente        | pendiente | pendiente   |

## Decisión

Pendiente de completar tras ejecutar la batería con los tres candidatos.

## Consecuencias

Pendiente de completar tras la selección final.
