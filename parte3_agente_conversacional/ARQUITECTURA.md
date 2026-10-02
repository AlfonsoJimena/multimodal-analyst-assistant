# Arquitectura de la parte 3 · Agente conversacional

Chatbot que responde preguntas en lenguaje natural sobre los datos de la
parte 2 (viajes de taxi de NYC repartidos en tres sedes). El agente
**solo habla con el coordinador** de la parte 2; nunca accede a las
`site_api` ni a Postgres directamente.

## 1. Diagrama

```
┌────────────┐   HTTP /chat    ┌──────────────────────────────────────┐
│  Interfaz  │ ───────────────▶│            API del agente             │
│ (Streamlit)│                 │              (FastAPI)                │
│  :8501     │◀─────────────── │               :8300                   │
└────────────┘  ChatResponse   │                                       │
                               │  ┌─────────────────────────────────┐  │
                               │  │     Orquestador (tool calling)  │  │
                               │  │  bucle LLM <-> herramientas     │  │
                               │  └───────┬──────────────┬──────────┘  │
                               │          │              │             │
                               │   ┌──────▼─────┐  ┌─────▼─────────┐   │
                               │   │    LLM     │  │  Herramientas │   │
                               │   │ (OpenRouter)│ │  (src/tools)  │   │
                               │   └────────────┘  └─────┬─────────┘   │
                               │                         │             │
                               │                 ┌───────▼─────────┐   │
                               │                 │  Capa de datos  │   │
                               │                 │   (src/data)    │   │
                               │                 │ failover+privac.│   │
                               └─────────────────────────┬───────────┘
                                                          │ HTTP
                        ┌─────────────────────────────────▼──────────────┐
                        │   Coordinador de la parte 2 (failover de sedes) │
                        │  central :8100 · chamartin :8101 · atocha :8102 │
                        │           (o el mock :8190 en desarrollo)       │
                        └─────────────────────────────────────────────────┘
```

## 2. Componentes

| Carpeta | Contenido | Issue |
|---|---|---|
| `src/api/` | `schemas.py` (contrato de /chat), `main.py` (FastAPI) | P3-01, P3-11 |
| `src/agent/` | `config.py`, `llm.py`, `orchestrator.py`, `prompts.py` | P3-01, P3-08/09/10 |
| `src/tools/` | `base.py` (formato+registro) y las herramientas | P3-01, P3-06/07 |
| `src/data/` | cliente del coordinador, agregacion, privacidad | P3-04 |
| `src/knowledge/` | zonas de NYC, glosario, tipos de pago | P3-05 |
| `src/ui/` | interfaz Streamlit | P3-12/13 |
| `mock/` | coordinador falso para desarrollar y testear sin la parte 2 | P3-03 |

## 3. Contratos compartidos (definidos en P3-01)

- **`/chat`**: recibe `ChatRequest {session_id, message}` y devuelve
  `ChatResponse {request_id, reply, blocks, sources, warnings, latency_ms}`.
- **`Block {type: kpi|table|line|bar, title, data, unit?}`**: bloque visual.
- **`Source {tool, args, served_by, sites_ok, sites_failed, partial, latency_ms}`**:
  trazabilidad de cada llamada a herramienta.
- **Herramientas** (`src/tools/base.py`): devuelven `ToolResult {data, meta, block}`
  o `ToolError {error, detail}`, con `ToolMeta {sites_ok, sites_failed, partial,
  served_by, period, note}`. El registro genera el esquema JSON de tool calling.

**Regla de oro:** las cifras de `blocks` y los `warnings` salen SIEMPRE del
código (de las herramientas), nunca del texto del LLM.

## 4. Contrato con la parte 2

- El agente consume el **coordinador**, que combina las tres sedes y hace
  failover. No se tocan las `site_api` ni la base de datos.
- Endpoints usados: `/metrics/hourly`, `/metrics/daily`, `/metrics/zone`,
  `/metrics/payment` y `/health` de cada réplica.
- P3-02 añade `breakdown=site` al coordinador para poder comparar sedes.
- Los importes llegan como **texto** (Decimal serializado) y se calculan con
  `Decimal`, nunca con `float`. Las medias se calculan como Σsumas / Σconteos.

## 5. Puertos reservados

| Servicio | Puerto |
|---|---|
| API del agente | 8300 |
| Interfaz (Streamlit) | 8501 |
| Coordinador mock | 8190 |

No se tocan los de la parte 2: site_api 8000–8002, coordinadores 8100–8102,
Postgres 5432–5434, métricas 9000–9002, Prometheus 9090, Grafana 3000.

## 6. Decisiones

- **El agente solo habla con el coordinador**, no con las sedes: respeta la
  arquitectura de la parte 2 y no duplica la lógica de combinación.
- **Mock propio** (P3-03) con la misma interfaz que el coordinador real: la
  parte 2 completa consume 8–9 GB y la CI no puede levantarla.
- **LLM vía OpenRouter** (API compatible con OpenAI): cambiar de modelo es
  cambiar una variable de entorno.
- **Privacidad**: se ocultan celdas con menos de `MIN_TRIPS_PER_CELL` viajes;
  no existen datos de viajes individuales, conductores ni pasajeros.
